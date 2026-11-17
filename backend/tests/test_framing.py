"""Enquadramento do modelo grande (app/services/framing.py = preprocess.py do notebook de tratamento).

A equivalência pixel a pixel com o código do notebook foi conferida rodando os dois lado a lado (docs/12). Aqui ficam as
propriedades que não podem mudar sem retreinar o ResNet.
"""
import numpy as np
import pytest
from PIL import Image

from app.services import framing as fr
from app.services.server_model import ServerModel, try_load
from tests.server_tiny_model import build_server_model

RNG = np.random.default_rng(0)


def scene(h, w, bg=(60, 140, 50), panel=(30, 60, 140), box=None):
    img = np.clip(np.array(bg)[None, None] + RNG.normal(0, 12, (h, w, 3)), 0, 255).astype(np.uint8)
    if box:
        y0, x0, y1, x1 = box
        img[y0:y1, x0:x1] = np.clip(np.array(panel)[None, None] + RNG.normal(0, 8, (y1 - y0, x1 - x0, 3)), 0, 255)
    return img


def test_crops_around_the_panel():
    img = scene(480, 640, box=(100, 150, 380, 500))
    out, info = fr.frame_image(img)
    assert out.shape == (224, 224, 3) and out.dtype == np.uint8 and info["metodo"] == "placa+recorte"
    hsv_blue = (out[..., 2].astype(int) - out[..., 1]) > 40                     # pixels azuis da placa
    assert hsv_blue.mean() > 0.5                                                # a placa passa a ocupar a maior parte


@pytest.mark.parametrize("img,metodo", [
    (scene(300, 900, bg=(200, 180, 120), box=(60, 30, 240, 870)), "placa+fundo_desfocado"),   # placa muito larga
    (scene(400, 600, bg=(200, 120, 40)), "central+recorte"),                                  # sem placa
    (scene(200, 800, bg=(200, 120, 40)), "central+fundo_desfocado"),                          # foto larga sem placa
])
def test_other_paths(img, metodo):
    out, info = fr.frame_image(img)
    assert out.shape == (224, 224, 3) and info["metodo"] == metodo


def test_removes_black_bars_and_keeps_colors():
    img = scene(500, 500, box=(120, 100, 380, 400))
    img[:60] = 0
    img[-60:] = 0
    out, _ = fr.frame_image(img)
    assert (out.reshape(-1, 3).sum(axis=1) < 15).mean() < 0.01                  # quase nada da tarja preta
    solid = np.full((300, 300, 3), (200, 100, 50), np.uint8)
    assert (fr.frame_image(solid)[0] == (200, 100, 50)).all()                   # nenhuma mudança de cor


def test_server_model_uses_framing_by_default(server_model):
    assert server_model.framing == "panel"
    p = server_model.predict(Image.fromarray(scene(480, 640, box=(100, 150, 380, 500))))
    assert p.framing == "placa+recorte"


def test_framing_none_stretches(tmp_path):
    m = ServerModel.load(build_server_model(tmp_path / "a"), framing="none")
    p = m.predict(Image.fromarray(scene(480, 640, box=(100, 150, 380, 500))))
    assert m.framing == "none" and p.framing is None


def test_card_overrides_framing_and_invalid_is_rejected(tmp_path):
    d = build_server_model(tmp_path / "b", extra_card={"preprocessamento": {"img_size": 32, "enquadramento": "center"}})
    assert ServerModel.load(d, framing="panel").framing == "center"
    bad = build_server_model(tmp_path / "c", extra_card={"preprocessamento": {"img_size": 32, "enquadramento": "xyz"}})
    model, why = try_load(str(bad))
    assert model is None and "enquadramento" in why
