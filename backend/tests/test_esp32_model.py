"""O modelo do ESP32 (models/esp32, soilnet 2x) e tudo que precisa bater com ele.

1. Coerência: o que o firmware compila (config.h + model_data.h) é o mesmo modelo e os mesmos valores do model_card.json,
   e o backend usa o mesmo tamanho de entrada. Se alguém trocar um e esquecer o outro, este teste quebra.
2. Caminho completo: backend → HTTP → ESP32 simulado com o modelo REAL → resposta → banco, incluindo a bomba.
   As imagens são sintéticas (fixtures/esp32/LEIA.md): provam o encanamento, não a acurácia.
"""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("ai_edge_litert")

from app.api.routes import create_app                                            # noqa: E402
from app.config import Settings                                                  # noqa: E402
from app.services.assistant.service import Assistant                             # noqa: E402
from app.services.esp32 import Esp32Client                                       # noqa: E402
from app.services.storage import ImageStore                                      # noqa: E402
from esp32_simulator.server import Device, serve                                 # noqa: E402
from esp32_simulator.tflite_engine import TFLiteEngine                           # noqa: E402
from tests.conftest import KEY, post                                             # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models" / "esp32"
SRC = ROOT / "firmware" / "esp32" / "src"
IMGS = Path(__file__).parent / "fixtures" / "esp32"
CARD = json.loads((MODEL / "model_card.json").read_text(encoding="utf-8"))


def config_h() -> dict:
    text = (SRC / "config.h").read_text(encoding="utf-8")
    num = lambda name: re.search(rf"\b{name}\s*=\s*([0-9.]+)f?;", text).group(1)
    return {"INPUT_SIZE": int(num("INPUT_SIZE")), "NUM_CLASSES": int(num("NUM_CLASSES")),
            "POSITIVE_CLASS": int(num("POSITIVE_CLASS")), "DECISION_THRESHOLD": float(num("DECISION_THRESHOLD")),
            "CONF_THRESHOLD": float(num("CONF_THRESHOLD")),
            "MODEL_VERSION": re.search(r'#define MODEL_VERSION "([^"]+)"', text).group(1),
            "CLASS_NAMES": re.findall(r'"(\w+)"', re.search(r"CLASS_NAMES\[NUM_CLASSES\] = \{([^}]*)\}", text).group(1))}


def test_firmware_compiles_this_model():
    header = (SRC / "model_data.h").read_text(encoding="utf-8")
    data = bytes(int(b, 16) for b in re.findall(r"0x([0-9a-f]{2})", header.split("{", 1)[1].split("}", 1)[0]))
    assert data == (MODEL / "model.tflite").read_bytes()                         # model_data.h = models/esp32/model.tflite
    assert f"g_model_data_len = {len(data)};" in header and len(data) == CARD["tflite_bytes"]


def test_config_h_matches_the_model_card():
    c = config_h()
    labels = json.loads((MODEL / "labels.json").read_text(encoding="utf-8"))
    assert labels == CARD["labels"] == ["NAOLIMPAR", "LIMPAR"]
    assert c["MODEL_VERSION"] == CARD["version"]
    assert c["INPUT_SIZE"] == CARD["input_size"] == CARD["tflite"]["input"]["shape"][1]
    assert c["NUM_CLASSES"] == len(labels) == 2 and c["CLASS_NAMES"] == ["LIMPO", "SEVERO"]
    assert c["POSITIVE_CLASS"] == labels.index(CARD["positive_label"]) == 1
    assert c["DECISION_THRESHOLD"] == CARD["limiar_limpar"]
    assert c["CONF_THRESHOLD"] == CARD["low_confidence_threshold"]


def test_backend_defaults_match_the_model():
    s = Settings()
    assert s.input_size == CARD["input_size"] and s.esp32_classes == ("LIMPO", "SEVERO") and s.jpeg_quality == CARD["jpeg_quality"]
    assert s.esp32_framing == "panel" and "tratado 224" in CARD["preprocessamento"]   # treinado com fotos enquadradas
    assert s.low_confidence_threshold == CARD["low_confidence_threshold"]       # "revisar" no backend = abaixo da trava da bomba


@pytest.fixture(scope="module")
def engine():
    return TFLiteEngine.load(MODEL)


def test_simulator_reads_the_model(engine):
    assert engine.names == ("LIMPO", "SEVERO") and engine.positive == 1 and engine.binary and engine.rgb565
    assert engine.size == 112 and engine.version == CARD["version"]
    assert engine.decision_threshold == CARD["limiar_limpar"] and engine.threshold == CARD["low_confidence_threshold"]


@pytest.fixture
def stack(repo, tmp_path, engine):
    dev = Device(engine, key="chave-esp", pump_ms=3000, cooldown_s=3600)
    srv = serve(dev, "127.0.0.1", 0)
    cfg = Settings(admin_api_key="segredo", storage_dir=str(tmp_path / "img"), esp32_key="chave-esp")   # padrões de produção
    app = create_app(cfg, repo=repo, esp32=Esp32Client(f"http://127.0.0.1:{srv.server_address[1]}", "chave-esp", classes=cfg.esp32_classes),
                     assistant=Assistant(None), store=ImageStore(cfg.storage_dir))
    with TestClient(app) as c:
        yield c
    srv.shutdown()


def test_full_path_backend_to_simulated_esp32(stack):
    limpo = post(stack, (IMGS / "modelo_diz_limpo.jpg").read_bytes(), headers=KEY).json()["analise"]
    assert limpo["classification"] == "LIMPO" and not limpo["cleaning_activated"] and limpo["model_version"] == CARD["version"]
    severo = post(stack, (IMGS / "modelo_diz_severo.jpg").read_bytes(), headers=KEY).json()["analise"]
    assert severo["classification"] == "SEVERO" and severo["cleaning_activated"] and severo["pump_duration_ms"] == 3000
    assert set(severo["probs"]) == {"LIMPO", "SEVERO"} and severo["confidence"] >= CARD["low_confidence_threshold"]
    again = post(stack, (IMGS / "modelo_diz_severo.jpg").read_bytes(), headers=KEY).json()["analise"]
    assert not again["cleaning_activated"] and "intervalo" in again["pump_reason"]                 # intervalo mínimo
    blocked = post(stack, (IMGS / "modelo_diz_severo.jpg").read_bytes()).json()                   # sem X-API-Key
    assert blocked["bomba_bloqueada_por_falta_de_chave"] and not blocked["analise"]["cleaning_activated"]


def test_simulator_accepts_system_names_in_labels_json(tmp_path):
    """labels.json já com os nomes do sistema (["LIMPO","SEVERO"]) também é binário, com SEVERO positiva; 3 classes é recusado."""
    import shutil
    from PIL import Image
    shutil.copy(MODEL / "model.tflite", tmp_path / "model.tflite")
    card = dict(CARD)
    card.pop("positive_label")
    (tmp_path / "model_card.json").write_text(json.dumps(card))
    (tmp_path / "labels.json").write_text('["LIMPO", "SEVERO"]')
    e = TFLiteEngine.load(tmp_path)
    assert e.names == ("LIMPO", "SEVERO") and e.positive == 1
    assert e.predict_image(Image.new("RGB", (112, 112), (90, 90, 90))).label in {"LIMPO", "SEVERO"}
    (tmp_path / "labels.json").write_text('["LIMPO", "MODERADO", "SEVERO"]')
    with pytest.raises(ValueError, match="binário"):
        TFLiteEngine.load(tmp_path)


def test_operating_threshold_is_not_argmax():
    from esp32_simulator.tflite_engine import pick_binary
    assert pick_binary(0.45, 0.41) == (True, 0.45)           # 0,45 >= 0,41: positiva, mesmo perdendo no argmax
    assert pick_binary(0.50, 0.50)[0] is True                # no limiar: positiva
    pos, conf = pick_binary(0.39, 0.41)
    assert pos is False and conf == pytest.approx(0.61)


def test_rgb565_expansion_matches_the_firmware():
    import numpy as np
    from esp32_simulator.tflite_engine import to_rgb565
    out = to_rgb565(np.array([[[255, 255, 255], [0, 0, 0], [128, 128, 128], [7, 3, 7]]]))
    assert out.astype(int).tolist() == [[[255, 255, 255], [0, 0, 0], [132, 130, 132], [0, 0, 0]]]   # (r5<<3)|(r5>>2), (g6<<2)|(g6>>4)
