"""A SAÍDA do pipeline de treino do ESP32 (ai-model/training/train.py, binário) funciona no simulador e no backend.

O modelo em fixtures/tiny-cnn-112-sintetico/ foi gerado por train.py com dados sintéticos (veja o LEIA.md da pasta):
prova o FORMATO (labels.json, model_card.json, .tflite int8, limiar, trava da bomba), não a acurácia.
Compara também com o soilnet v1, o modelo que já rodou no ESP32: o que o firmware usa tem que ser igual.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("ai_edge_litert")

from app.api.routes import create_app                                            # noqa: E402
from app.config import Settings                                                  # noqa: E402
from app.services.assistant.service import Assistant                             # noqa: E402
from app.services.esp32 import Esp32Client                                      # noqa: E402
from app.services.storage import ImageStore                                      # noqa: E402
from esp32_simulator.server import Device, serve                                 # noqa: E402
from esp32_simulator.tflite_engine import TFLiteEngine                           # noqa: E402
from tests.conftest import KEY, post                                             # noqa: E402

FIX = Path(__file__).parent / "fixtures"
TRAINED, SOILNET = FIX / "tiny-cnn-112-sintetico", FIX / "soilnet-112"


@pytest.fixture(scope="module")
def engine():
    return TFLiteEngine.load(TRAINED)


def test_same_contract_as_the_soilnet_that_runs_on_the_esp32(engine):
    new, ref = (json.loads((d / "model_card.json").read_text(encoding="utf-8")) for d in (TRAINED, SOILNET))
    assert json.loads((TRAINED / "labels.json").read_text()) == json.loads((SOILNET / "labels.json").read_text()) == ["NAOLIMPAR", "LIMPAR"]
    for k in ("task", "input_size", "labels", "positive_label", "resize_mode", "jpeg_quality", "rgb565"):
        assert new[k] == ref[k], k
    for side in ("input", "output"):                                             # o que o firmware lê do tensor
        assert {k: new["tflite"][side][k] for k in ("shape", "dtype", "scale", "zero_point")} == \
               {k: ref["tflite"][side][k] for k in ("shape", "dtype", "scale", "zero_point")}
    assert engine.names == ("LIMPO", "SEVERO") and engine.positive == 1 and engine.binary and engine.rgb565 and engine.size == 112
    assert new["low_confidence_threshold"] >= 0.5                                # trava da bomba do pipeline novo


def test_ops_known_by_the_firmware(engine):
    ops = set(json.loads((TRAINED / "model_card.json").read_text())["tflite"]["ops"])
    soilnet_ops = set(json.loads((SOILNET / "model_card.json").read_text())["tflite"]["ops"])
    assert ops - soilnet_ops <= {"MUL"}                                          # MUL vem do Rescaling; o resto já rodou na placa


@pytest.fixture
def stack(repo, tmp_path, engine):
    dev = Device(engine, key="chave-esp", pump_ms=3000, cooldown_s=3600)
    srv = serve(dev, "127.0.0.1", 0)
    cfg = Settings(admin_api_key="segredo", input_size=112, esp32_classes=("LIMPO", "SEVERO"), storage_dir=str(tmp_path / "img"),
                   esp32_key="chave-esp")
    app = create_app(cfg, repo=repo, esp32=Esp32Client(f"http://127.0.0.1:{srv.server_address[1]}", "chave-esp", classes=cfg.esp32_classes),
                     assistant=Assistant(None), store=ImageStore(cfg.storage_dir))
    with TestClient(app) as c:
        yield c
    srv.shutdown()


def test_full_path_backend_to_simulated_esp32(stack):
    clean = post(stack, (TRAINED / "limpa.jpg").read_bytes(), headers=KEY).json()["analise"]
    assert clean["classification"] == "LIMPO" and not clean["cleaning_activated"] and clean["model_version"].startswith("tiny_cnn-112")
    dirty = post(stack, (TRAINED / "suja.jpg").read_bytes(), headers=KEY).json()["analise"]
    assert dirty["classification"] == "SEVERO" and dirty["cleaning_activated"] and dirty["pump_duration_ms"] == 3000
    again = post(stack, (TRAINED / "suja.jpg").read_bytes(), headers=KEY).json()["analise"]
    assert again["classification"] == "SEVERO" and not again["cleaning_activated"] and "intervalo" in again["pump_reason"]
    assert set(dirty["probs"]) == {"LIMPO", "SEVERO"}


def test_pump_floor_blocks_an_unsure_positive(engine):
    """Limiar de decisão baixo classifica "Precisa limpar" cedo, mas a bomba só aciona com P >= low_confidence_threshold."""
    dev = Device(engine, key="", pump_ms=3000, cooldown_s=1, threshold=0.5)
    engine_threshold = engine.decision_threshold
    try:
        engine.decision_threshold = 0.05
        on, _, why = dev.decide("SEVERO", 0.3, True)
        assert not on and "confiança baixa" in why
        assert dev.decide("SEVERO", 0.9, True)[0]
    finally:
        engine.decision_threshold = engine_threshold


def test_simulator_accepts_system_names_in_labels_json(tmp_path):
    """Regressão: labels.json já com os nomes do sistema (["LIMPO","SEVERO"]) também é binário, com SEVERO positiva."""
    import shutil
    from PIL import Image
    for n in ("model.tflite", "model_card.json"):
        shutil.copy(TRAINED / n, tmp_path / n)
    card = json.loads((tmp_path / "model_card.json").read_text())
    card.pop("positive_label")
    (tmp_path / "model_card.json").write_text(json.dumps(card))
    (tmp_path / "labels.json").write_text('["LIMPO", "SEVERO"]')
    e = TFLiteEngine.load(tmp_path)
    assert e.names == ("LIMPO", "SEVERO") and e.positive == 1
    assert e.predict_image(Image.open(TRAINED / "suja.jpg")).label == "SEVERO"
    (tmp_path / "labels.json").write_text('["LIMPO", "MODERADO", "SEVERO"]')
    with pytest.raises(ValueError, match="binário"):
        TFLiteEngine.load(tmp_path)
