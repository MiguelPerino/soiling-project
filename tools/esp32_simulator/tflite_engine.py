"""Motor TFLite int8 do simulador: quantiza e desquantiza como o firmware faz, para que o simulador se comporte
como o dispositivo real (a menos de diferenças de arredondamento entre as bibliotecas).

Usa `ai_edge_litert` ou `tflite_runtime` se existirem (leves); senão `tensorflow.lite`.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from esp32_simulator.classifier import LABELS, Prediction


def _interpreter(path: str):
    for mod, attr in (("ai_edge_litert.interpreter", "Interpreter"), ("tflite_runtime.interpreter", "Interpreter")):
        try:
            return getattr(__import__(mod, fromlist=[attr]), attr)(model_path=path)
        except ImportError:
            continue
    import tensorflow as tf
    return tf.lite.Interpreter(model_path=path)


def to_rgb565(rgb: np.ndarray) -> np.ndarray:
    """Trunca para RGB565 e expande de volta a 8 bits (replicando os bits altos), como o firmware faz ao decodificar o JPEG
    em RGB565. Só é aplicado se o model_card diz "rgb565": true (o treino já passou por isso)."""
    q = np.asarray(rgb).astype(np.int32)
    r, g, b = q[..., 0] >> 3, q[..., 1] >> 2, q[..., 2] >> 3
    out = np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1)
    return out.astype(np.float32)


def pick_binary(p_pos: float, threshold: float) -> tuple[bool, float]:
    """Regra do firmware para modelo binário (firmware/esp32/src/decision.h): P(positiva) >= limiar => positiva.
    Devolve (é_positiva, confiança_da_classe_escolhida). Não é argmax: com limiar 0,41, P(positiva)=0,45 já é positiva."""
    return (True, p_pos) if p_pos >= threshold else (False, 1.0 - p_pos)


class TFLiteEngine:
    """Modelo TFLite do ESP32. Dois formatos de modelo:
      - 3 classes (LIMPO, MODERADO, SEVERO): argmax; a bomba exige `low_confidence_threshold`.
      - binário (2 saídas, ex.: NAOLIMPAR/LIMPAR): a classe negativa vira LIMPO e a positiva (card: positive_label) vira SEVERO,
        que são os nomes do sistema; vale o limiar de operação `limiar_limpar` do card (como no firmware).
    """

    def __init__(self, interp, card: dict, names: tuple[str, ...] | None = None, positive: int | None = None) -> None:
        self.it = interp
        self.it.allocate_tensors()
        self.i = self.it.get_input_details()[0]
        self.o = self.it.get_output_details()[0]
        self.card = card
        self.version = str(card.get("version", "desconhecida"))
        self.size = int(card.get("input_size", self.i["shape"][1]))
        self.names = tuple(names) if names else LABELS
        self.positive = positive                      # índice da classe positiva (só no binário)
        self.binary = len(self.names) == 2
        self.rgb565 = bool(card.get("rgb565", False))
        self.decision_threshold = float(card.get("limiar_limpar", 0.5))
        self.threshold = float(card.get("low_confidence_threshold", self.decision_threshold if self.binary else 0.6))

    @classmethod
    def load(cls, model_dir: str | Path) -> "TFLiteEngine":
        d = Path(model_dir)
        labels = json.loads((d / "labels.json").read_text(encoding="utf-8"))
        card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
        if labels == list(LABELS):
            return cls(_interpreter(str(d / "model.tflite")), card)
        if len(labels) == 2:
            pos_name = card.get("positive_label") or ("SEVERO" if "SEVERO" in labels else labels[1])
            if pos_name not in labels:
                raise ValueError(f"positive_label {pos_name!r} não está em labels.json {labels}")
            positive = labels.index(pos_name)
            names = ["LIMPO", "LIMPO"]
            names[positive] = "SEVERO"                # a classe que aciona a bomba é SEVERO; a outra, LIMPO
            return cls(_interpreter(str(d / "model.tflite")), card, tuple(names), positive)
        raise ValueError(f"labels.json {labels} não é um formato conhecido (3 classes do sistema ou 2 classes)")

    def predict_image(self, img: Image.Image) -> Prediction:
        t0 = time.perf_counter()
        rgb = np.asarray(img.convert("RGB").resize((self.size, self.size), Image.BILINEAR), dtype=np.float32)
        if self.rgb565:
            rgb = to_rgb565(rgb)
        si, zi = self.i["quantization"]
        q = np.clip(np.round(rgb / si + zi), -128, 127).astype(np.int8)[None]
        self.it.set_tensor(self.i["index"], q)
        self.it.invoke()
        so, zo = self.o["quantization"]
        p = (self.it.get_tensor(self.o["index"])[0].astype(np.float32) - zo) * so
        if self.binary:
            is_pos, _ = pick_binary(float(p[self.positive]), self.decision_threshold)
            idx = self.positive if is_pos else 1 - self.positive
            conf = float(p[idx])                       # probabilidade que o modelo deu à classe escolhida (igual ao firmware)
        else:
            idx = int(p.argmax())
            conf = float(p[idx])
        return Prediction(label=self.names[idx], confidence=conf, probs={self.names[i]: float(p[i]) for i in range(len(p))},
                          low_confidence=conf < self.threshold, latency_ms=(time.perf_counter() - t0) * 1000,
                          model_version=self.version)
