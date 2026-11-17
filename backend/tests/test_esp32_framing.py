"""ESP32_FRAMING: o que o backend envia ao ESP32. Protocolo igual (JPEG size×size); muda só o conteúdo da imagem.

panel (padrão; soilnet 2x de 16/11, treinado com o dataset tratado 224): enquadra como o notebook de tratamento, grava como o
      dataset (JPEG 95, 4:4:4) e reduz para 112 — o mesmo caminho do device_like do notebook treino_esp32_dataset224.
none  estica a foto inteira (o comportamento antigo, para modelos do dataset bruto), byte a byte.
"""
from io import BytesIO

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import create_app
from app.config import Settings
from app.services import framing as fr
from app.services.analysis import esp32_jpeg
from app.services.assistant.service import Assistant
from app.services.esp32 import Esp32Client
from app.services.storage import ImageStore
from tests.conftest import KEY, post


def scene(h=480, w=640):
    """Gramado com uma placa azul pequena no canto: esticar mantém o gramado; enquadrar recorta a placa."""
    rng = np.random.default_rng(1)
    img = np.clip(np.array([60, 140, 50]) + rng.normal(0, 12, (h, w, 3)), 0, 255).astype(np.uint8)
    img[60:300, 80:360] = np.clip(np.array([30, 60, 140]) + rng.normal(0, 8, (240, 280, 3)), 0, 255)
    return Image.fromarray(img)


def blue_share(jpeg: bytes) -> float:
    a = np.asarray(Image.open(BytesIO(jpeg)).convert("RGB")).astype(int)
    return float(((a[..., 2] - a[..., 1]) > 40).mean())


def test_none_is_the_old_behavior_byte_by_byte():
    img = scene()
    buf = BytesIO()
    img.resize((112, 112), Image.BILINEAR).save(buf, "JPEG", quality=85)          # o esp32_jpeg de antes do soilnet 2x
    assert esp32_jpeg(img, 112, 85, "none") == buf.getvalue()


def test_default_is_panel():
    img = scene()
    assert esp32_jpeg(img, 112, 85) == esp32_jpeg(img, 112, 85, "panel")


def test_panel_frames_like_the_training_notebook():
    img = scene()
    stretched, framed = esp32_jpeg(img, 112, 85, "none"), esp32_jpeg(img, 112, 85, "panel")
    assert Image.open(BytesIO(framed)).size == (112, 112)                         # mesmo protocolo
    assert blue_share(framed) > 0.6 > blue_share(stretched)                       # a placa passa a ocupar a imagem
    # o caminho do notebook, passo a passo: frame_image (tratamento) -> save_jpg 95 4:4:4 (dataset) -> device_like
    tratada = BytesIO()
    Image.fromarray(fr.frame_image(np.asarray(img), 224, "panel")[0]).save(tratada, "JPEG", quality=95, subsampling=0)
    expected = Image.open(BytesIO(tratada.getvalue())).convert("RGB").resize((112, 112), Image.BILINEAR)
    buf = BytesIO(); expected.save(buf, "JPEG", quality=85)
    assert framed == buf.getvalue()                                               # 224 tratada -> 112 -> JPEG 85


def test_settings_validate_framing(monkeypatch):
    monkeypatch.delenv("ESP32_FRAMING", raising=False)
    assert Settings.from_env().esp32_framing == "panel"
    monkeypatch.setenv("ESP32_FRAMING", "None")
    assert Settings.from_env().esp32_framing == "none"
    monkeypatch.setenv("ESP32_FRAMING", "xyz")
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("framing", ["none", "panel"])
def test_backend_sends_what_the_setting_says(repo, tmp_path, framing):
    seen = []

    def esp(request: httpx.Request):
        seen.append(request.content)
        return httpx.Response(200, json={"classification": "LIMPO", "confidence": 0.9, "probs": {"LIMPO": 0.9, "SEVERO": 0.1}})
    cfg = Settings(admin_api_key="segredo", input_size=112, storage_dir=str(tmp_path / "img"), esp32_framing=framing)
    app = create_app(cfg, repo=repo, esp32=Esp32Client("http://esp.local", transport=httpx.MockTransport(esp)),
                     assistant=Assistant(None), store=ImageStore(cfg.storage_dir))
    buf = BytesIO(); scene().save(buf, "JPEG", quality=95)
    with TestClient(app) as c:
        assert c.get("/api/config").json()["engines"]["esp32"]["enquadramento"] == framing
        assert post(c, buf.getvalue(), headers=KEY, pump="false").status_code == 200
    assert Image.open(BytesIO(seen[0])).size == (112, 112)
    assert (blue_share(seen[0]) > 0.6) == (framing == "panel")
