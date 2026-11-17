"""Testes das partes puras do pipeline de dados (sem TensorFlow). O modelo do ESP32 é BINÁRIO (LIMPO/SEVERO)."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
from labels import LABELS, MODEL_NAMES, POSITIVE, parse_class_map, to_label  # noqa: E402
from metrics import auc, choose_threshold, predict, selective, summarize  # noqa: E402
import prepare_data  # noqa: E402
import train  # noqa: E402  (importa sem TensorFlow: TF só é carregado dentro das funções)


def test_labels_are_binary_and_match_the_firmware():
    assert LABELS == ("LIMPO", "SEVERO") and MODEL_NAMES == ("NAOLIMPAR", "LIMPAR") and POSITIVE == 1
    cfg = (ROOT / "firmware/esp32/src/config.h").read_text(encoding="utf-8")
    assert 'CLASS_NAMES[NUM_CLASSES] = {"LIMPO", "SEVERO"}' in cfg and "POSITIVE_CLASS      = 1;" in cfg
    assert "NUM_CLASSES         = 2;" in cfg


def test_class_map():
    m = parse_class_map("")
    for name, label in [("Clean", "LIMPO"), ("NaoLimpar", "LIMPO"), ("LIMPO", "LIMPO"),
                        ("Soiled", "SEVERO"), ("Limpar", "SEVERO"), ("SEVERO", "SEVERO")]:
        assert to_label(name, m) == label
    with pytest.raises(ValueError, match="Dusty=SEVERO"):            # poeira não tem padrão no sistema binário
        to_label("Dusty", m)
    assert to_label("dusty", parse_class_map("Dusty=SEVERO")) == "SEVERO"
    for bad in ("X=OUTRO", "Dusty=MODERADO"):
        with pytest.raises(ValueError):
            parse_class_map(bad)


def mk(p: Path, color):
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color).save(p)


def test_folder_and_csv_and_dedupe(tmp_path):
    root = tmp_path / "rf"
    for s, split in enumerate(("train", "valid", "test")):
        for i, cls in enumerate(("Clean", "Dusty", "Soiled")):
            mk(root / split / cls / "a.jpg", (i * 80, 10 + s * 30, i))
    mk(root / "train" / "Clean" / "dup.jpg", (0, 10, 0))                  # duplicata exata do a.jpg de treino
    with pytest.raises(ValueError):
        prepare_data.collect_roboflow(root, parse_class_map(""))           # Dusty sem decisão: recusa
    rows = prepare_data.collect_roboflow(root, parse_class_map("Dusty=SEVERO"))
    man = prepare_data.build(rows, 1, False)
    assert len(man) == 9 and {m["split"] for m in man} == {"train", "val", "test"}
    assert {m["label"] for m in man} == {"LIMPO", "SEVERO"}

    csv_root = tmp_path / "csv"
    mk(csv_root / "train" / "x.jpg", (1, 2, 3))
    mk(csv_root / "train" / "y.jpg", (9, 2, 3))
    with (csv_root / "train" / "_classes.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["filename", " Clean", " Soiled"])
        w.writerow(["x.jpg", 1, 0])
        w.writerow(["y.jpg", 1, 1])                                       # ambíguo: ignorado
    rows = prepare_data.collect_roboflow(csv_root, parse_class_map(""))
    assert [(p.name, l) for p, l, _ in rows] == [("x.jpg", "LIMPO")]


def test_extra_folders_from_notebook_and_backend_export(tmp_path):
    for i, cls in enumerate(("Limpar", "NaoLimpar", "LIMPO", "SEVERO")):
        mk(tmp_path / cls / "a.jpg", (i * 50, 0, 0))
    rows = prepare_data.collect_extra(tmp_path, parse_class_map(""))
    assert sorted(l for _, l, _ in rows) == ["LIMPO", "LIMPO", "SEVERO", "SEVERO"]


def test_resplit_is_stratified_and_deterministic(tmp_path):
    items = [(tmp_path / f"{c}{i}.jpg", c) for c in ("LIMPO", "SEVERO") for i in range(20)]
    a, b = prepare_data.stratified_split(items, 7), prepare_data.stratified_split(items, 7)
    assert a == b
    for c in ("LIMPO", "SEVERO"):
        assert sum(v == "test" for p, v in a.items() if p.name.startswith(c)) in (3,)


def test_metrics_binary():
    y = [0, 0, 0, 1, 1, 1]
    p = [0.1, 0.3, 0.45, 0.42, 0.8, 0.9]
    assert predict(p, 0.41).tolist() == [0, 0, 1, 1, 1, 1]               # limiar, não argmax: 0,42 já é SEVERO
    m = summarize(y, predict(p, 0.41))
    assert m["matriz_confusao"] == [[2, 1], [0, 3]] and m["ordem_classes"] == ["LIMPO", "SEVERO"]
    assert m["limpos_que_acionariam_pct"] == pytest.approx(1 / 3) and m["sujos_ignorados_pct"] == 0.0
    assert auc(y, p) == pytest.approx(8 / 9) and auc([0, 0], [0.1, 0.2]) is None
    t = choose_threshold(y, p)                                          # 0,31..0,42 e 0,46..0,80 empatam: vence o mais perto de 0,5
    assert t["limiar"] == 0.5 and t["f1_macro_validacao"] == pytest.approx(0.8286, abs=1e-3)
    t = choose_threshold([0, 0, 1, 1], [0.05, 0.2, 0.3, 0.9])          # separável só abaixo de 0,5: o limiar desce
    assert 0.2 < t["limiar"] <= 0.3 and t["f1_macro_validacao"] == 1.0
    s = selective(p, y, 0.41, 0.6)
    assert s["sujos_que_acionam_pct"] == pytest.approx(2 / 3) and s["limpos_que_acionam_pct"] == 0.0


def test_rgb565_matches_the_simulator_and_firmware():
    sys.path.insert(0, str(ROOT / "tools"))
    from esp32_simulator.tflite_engine import to_rgb565 as sim
    rng = np.random.default_rng(0)
    x = rng.integers(0, 256, (8, 8, 3)).astype(np.uint8)
    assert np.array_equal(train.to_rgb565(x), sim(x).astype(np.uint8))


def test_deploy_view_is_what_the_esp32_receives():
    img = Image.new("RGB", (300, 120), (200, 100, 50))
    v = train.deploy_view(img, 112, 85, rgb565=True)
    assert v.shape == (112, 112, 3) and v.dtype == np.uint8                      # esticada, sem recorte


def test_card_and_labels_follow_the_soilnet_format(tmp_path):
    """O card exportado tem os campos que o simulador lê e que o config.h espelha (mesmo formato do soilnet v1)."""
    test = {"acuracia": 0.9, "f1_macro": 0.9, "auc_roc": 0.95}
    card = train.build_card(version="tiny_cnn-112-x", arch="tiny_cnn", size=112, jpeg_quality=85, rgb565=True,
                            threshold=0.41, pump=0.41, params=1, blob_len=2, info={}, counts={}, weights={0: 1.0, 1: 1.0},
                            val_f1_float=0.9, val_f1_int8=0.9, test=test)
    ref = json.loads((ROOT / "backend/tests/fixtures/soilnet-112/model_card.json").read_text(encoding="utf-8"))
    for k in ("input_size", "labels", "positive_label", "resize_mode", "jpeg_quality", "rgb565", "limiar_limpar",
              "limiar_nao_limpar", "low_confidence_threshold", "task"):
        assert k in card and type(card[k]) is type(ref[k]), k
    assert card["labels"] == ref["labels"] and card["positive_label"] == ref["positive_label"] == "LIMPAR"
    snippet = train.config_h_snippet(card)
    assert "POSITIVE_CLASS      = 1;" in snippet and "DECISION_THRESHOLD  = 0.41f;" in snippet and '{"LIMPO", "SEVERO"}' in snippet


def test_detection_export_is_rejected(tmp_path):
    (tmp_path / "train" / "images").mkdir(parents=True)
    with pytest.raises(SystemExit):
        prepare_data.collect_roboflow(tmp_path, parse_class_map(""))
