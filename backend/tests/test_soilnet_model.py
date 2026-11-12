"""O modelo real do ESP32 (soilnet v1, binário, 112 px, TFLite int8) passando pelo simulador e pelo backend.

Usa imagens de cor sólida: isto prova o ENCANAMENTO (quantização, classes, limiar, bomba), NÃO a acurácia do modelo.
"""
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
from esp32_simulator.tflite_engine import TFLiteEngine, pick_binary, to_rgb565   # noqa: E402
from tests.conftest import KEY, make_jpeg, post                                  # noqa: E402

MODEL = Path(__file__).parent / "fixtures" / "soilnet-112"
BROWN, GRAY = (120, 90, 60), (128, 128, 128)       # com este modelo: marrom -> SEVERO, cinza -> LIMPO (cores sólidas, só encanamento)


@pytest.fixture(scope="module")
def engine():
    return TFLiteEngine.load(MODEL)


@pytest.fixture
def stack(repo, tmp_path, engine):
    dev = Device(engine, key="chave-esp", pump_ms=3000, cooldown_s=3600)
    srv = serve(dev, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    cfg = Settings(admin_api_key="segredo", input_size=112, esp32_classes=("LIMPO", "SEVERO"), storage_dir=str(tmp_path / "img"),
                   esp32_key="chave-esp")
    app = create_app(cfg, repo=repo, esp32=Esp32Client(url, "chave-esp", classes=cfg.esp32_classes), assistant=Assistant(None),
                     store=ImageStore(cfg.storage_dir))
    with TestClient(app) as c:
        yield c
    srv.shutdown()


def test_engine_reads_the_binary_card(engine):
    assert engine.names == ("LIMPO", "SEVERO") and engine.positive == 1 and engine.binary      # NAOLIMPAR->LIMPO, LIMPAR->SEVERO
    assert engine.size == 112 and engine.rgb565 and engine.decision_threshold == 0.41 and engine.threshold == 0.41
    assert engine.version == "soilnet-112-20261110"


def test_operating_threshold_is_not_argmax():
    assert pick_binary(0.45, 0.41) == (True, 0.45)           # 0,45 >= 0,41: positiva, mesmo perdendo no argmax
    assert pick_binary(0.41, 0.41)[0] is True                # no limiar: positiva
    pos, conf = pick_binary(0.39, 0.41)
    assert pos is False and conf == pytest.approx(0.61)


def test_rgb565_expansion_matches_the_firmware():
    import numpy as np
    out = to_rgb565(np.array([[[255, 255, 255], [0, 0, 0], [128, 128, 128], [7, 3, 7]]]))
    assert out.astype(int).tolist() == [[[255, 255, 255], [0, 0, 0], [132, 130, 132], [0, 0, 0]]]   # (r5<<3)|(r5>>2), (g6<<2)|(g6>>4)


def test_full_path_with_the_real_model(stack):
    c = stack
    cfg = c.get("/api/config").json()["engines"]["esp32"]
    assert cfg["input_size"] == 112 and cfg["classes"] == ["LIMPO", "SEVERO"]
    assert c.get("/api/devices/status").json()["info"]["input_size"] == 112

    a = post(c, make_jpeg(GRAY, size=(640, 480)), headers=KEY).json()["analise"]
    assert a["classification"] == "LIMPO" and set(a["probs"]) == {"LIMPO", "SEVERO"} and not a["cleaning_activated"]
    assert a["model_version"] == "soilnet-112-20261110" and (a["width"], a["height"]) == (512, 384)

    s = post(c, make_jpeg(BROWN, size=(640, 480), noise_seed=1), headers=KEY).json()["analise"]
    assert s["classification"] == "SEVERO" and s["confidence"] >= 0.41 and s["cleaning_activated"] and s["pump_duration_ms"] == 3000
    again = post(c, make_jpeg(BROWN, size=(640, 480), noise_seed=2), headers=KEY).json()["analise"]
    assert again["classification"] == "SEVERO" and not again["cleaning_activated"] and "intervalo" in again["pump_reason"]
    off = post(c, make_jpeg(BROWN, size=(640, 480), noise_seed=3), headers=KEY, pump="false").json()["analise"]
    assert not off["cleaning_activated"] and "pump=0" in off["pump_reason"]
    assert c.get("/api/stats").json()["limpezas_acionadas"] == 1
