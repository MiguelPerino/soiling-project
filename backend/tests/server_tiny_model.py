"""Modelo grande SINTÉTICO para testes, no MESMO formato do ResNet50 do time (não é um classificador de painéis).

Igual ao modelo real: entrada "input" NHWC (N,H,W,3) float32 RGB 0..255, saída "probs" (N,2) já com softmax,
labels.json ["NaoLimpar","Limpar"] e model_card.json no formato do notebook (classe_positiva, decisao.limiar, onnx.input...).
Decide pela cor: canal R -> NaoLimpar, canal B -> Limpar. P(Limpar) = sigmoide((B - R) * 8 / 255).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

VERSION = "resnet-sintetico-teste"


def p_limpar(rgb: tuple[int, int, int]) -> float:
    return float(1.0 / (1.0 + np.exp(-(rgb[2] - rgb[0]) * 8.0 / 255.0)))


def build_server_model(dir_: str | Path, size: int = 32, threshold: float = 0.19, labels=("NaoLimpar", "Limpar"),
                       positive: str | None = "Limpar", outputs: int = 2, extra_card: dict | None = None) -> Path:
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    w = np.zeros((3, outputs), dtype=np.float32)
    w[0, 0] = w[2, 1] = 8.0 / 255.0                              # R -> saída 0 (NaoLimpar), B -> saída 1 (Limpar)
    nodes = [
        helper.make_node("ReduceMean", ["input"], ["mean"], axes=[1, 2], keepdims=0),
        helper.make_node("Gemm", ["mean", "W", "B"], ["logits"]),
        helper.make_node("Softmax", ["logits"], ["probs"], axis=1),
    ]
    graph = helper.make_graph(
        nodes, "tiny-server",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, ["batch", size, size, 3])],
        [helper.make_tensor_value_info("probs", TensorProto.FLOAT, ["batch", outputs])],
        initializer=[numpy_helper.from_array(w, "W"), numpy_helper.from_array(np.zeros(outputs, np.float32), "B")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.checker.check_model(model)
    onnx.save(model, d / "model.onnx")
    (d / "labels.json").write_text(json.dumps(list(labels)), encoding="utf-8")
    card = {
        "versao": VERSION, "arquitetura": "tiny-test", "labels": list(labels),
        "onnx": {"arquivo": "model.onnx",
                 "input": {"name": "input", "shape": ["batch", size, size, 3], "layout": "NHWC", "cor": "RGB", "faixa": [0, 255]},
                 "output": {"name": "probs", "shape": ["batch", outputs]}},
        "preprocessamento": {"img_size": size},
        "decisao": {"limiar": threshold, "criterio": "f1", "regra": "Limpar se P(Limpar) >= limiar"},
    }
    if positive is not None:
        card["classe_positiva"] = positive
    card.update(extra_card or {})
    (d / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    return d
