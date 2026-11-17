"""Modelo grande opcional (ex.: ResNet50) rodando NO SERVIDOR com ONNX Runtime (sem PyTorch/TensorFlow).

Classificação BINÁRIA: "Precisa limpar" (SEVERO) ou "Não precisa limpar" (LIMPO). Ele NUNCA aciona a bomba:
só o firmware do ESP32 decide isso.

Contrato do modelo (docs/12_MODELO_NO_SERVIDOR.md): uma pasta (SERVER_MODEL_DIR) com
    model.onnx        2 saídas. Entrada NHWC (N,H,W,3) ou NCHW (N,3,H,W), float32 RGB (o layout é lido do próprio ONNX)
    labels.json       os 2 nomes de classe na ordem das saídas, ex.: ["NaoLimpar","Limpar"] ou ["LIMPO","SEVERO"]
    model_card.json   o card que o notebook de treino gera (versao, classe_positiva, decisao.limiar, onnx.input/output...)

Regra de decisão (igual à do ESP32 binário, tools/esp32_simulator/tflite_engine.py):
    P(positiva) >= limiar  -> SEVERO (precisa limpar), senão LIMPO.
    confiança = probabilidade da classe escolhida.
    faixa de dúvida: limiar <= P(positiva) < revisao_ate -> SEVERO, mas marcado para revisão humana.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.labels import Label

DEFAULT_MEAN = (0.485, 0.456, 0.406)       # ImageNet (só se a entrada for 0..1 normalizada)
DEFAULT_STD = (0.229, 0.224, 0.225)
DEFAULT_SIZE = 224
DEFAULT_THRESHOLD = 0.5
DEFAULT_REVIEW_UNTIL = 0.5                 # PROVISÓRIO: topo da faixa de dúvida (SERVER_REVIEW_UNTIL)
SYSTEM_NAMES = {"LIMPO": Label.LIMPO, "SEVERO": Label.SEVERO}


class ServerModelUnavailable(RuntimeError):
    status = 503


@dataclass(frozen=True)
class ServerPrediction:
    label: Label
    confidence: float            # probabilidade da classe escolhida
    p_positive: float            # P(precisa limpar)
    low_confidence: bool         # caiu na faixa de dúvida
    probs: dict[str, float]      # {"LIMPO": ..., "SEVERO": ...}
    latency_ms: float
    model_version: str


def softmax(x: np.ndarray) -> np.ndarray:
    z = x - x.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def _get(d: dict, *path, default=None):
    for key in path:
        if not isinstance(d, dict) or key not in d:
            return default
        d = d[key]
    return d


def map_classes(names: list, card: dict) -> tuple[Label, Label]:
    """Traduz os 2 nomes do labels.json (ordem das saídas) para (LIMPO, SEVERO) do sistema.

    Aceita os nomes do sistema direto (["LIMPO","SEVERO"]) ou os do modelo + a classe positiva do card
    ("classe_positiva": "Limpar" -> SEVERO; a outra vira LIMPO).
    """
    if not isinstance(names, list) or len(names) != 2 or not all(isinstance(n, str) and n.strip() for n in names):
        raise ValueError(f"labels.json precisa ter exatamente 2 nomes de classe (recebi {names!r})")
    upper = [n.strip().upper() for n in names]
    if len(set(upper)) != 2:
        raise ValueError(f"classes repetidas em labels.json: {names}")
    if set(upper) == set(SYSTEM_NAMES):
        return tuple(SYSTEM_NAMES[u] for u in upper)                 # type: ignore[return-value]
    positive = card.get("classe_positiva") or card.get("positive_label")
    if not isinstance(positive, str) or positive.strip().upper() not in upper:
        raise ValueError(f"model_card.json precisa de 'classe_positiva' (a classe que significa 'precisa limpar') "
                         f"com um dos nomes de labels.json {names}")
    pos = upper.index(positive.strip().upper())
    return tuple(Label.SEVERO if i == pos else Label.LIMPO for i in range(2))   # type: ignore[return-value]


class ServerModel:
    def __init__(self, session, card: dict, labels: tuple[Label, Label], input_size: int = 0,
                 review_until: float | None = None) -> None:
        self.session, self.card, self.labels = session, card, labels
        inp, out = session.get_inputs()[0], session.get_outputs()[0]
        self.input_name = inp.name
        self.version = str(card.get("versao") or card.get("version") or "desconhecida")
        self.nhwc = _layout(inp.shape, card) == "NHWC"
        self.size = int(input_size or _get(card, "preprocessamento", "img_size") or card.get("input_size")
                        or _fixed_side(inp.shape, self.nhwc) or DEFAULT_SIZE)
        faixa = _get(card, "onnx", "input", "faixa") or card.get("input_range")
        self.raw_0_255 = isinstance(faixa, list) and len(faixa) == 2 and float(faixa[1]) > 1.0   # normalização dentro do ONNX
        self.mean = np.asarray(card.get("mean", DEFAULT_MEAN), dtype=np.float32)
        self.std = np.asarray(card.get("std", DEFAULT_STD), dtype=np.float32)
        self.outputs_probs = (card.get("output") == "probs" or _get(card, "onnx", "output", "name") == "probs"
                              or out.name == "probs")
        self.positive = labels.index(Label.SEVERO)
        self.threshold = float(_get(card, "decisao", "limiar", default=card.get("limiar", DEFAULT_THRESHOLD)))
        if not 0.0 < self.threshold < 1.0:
            raise ValueError(f"limiar de decisão fora de (0, 1): {self.threshold}")
        ru = _get(card, "decisao", "revisao_ate")
        ru = float(ru if ru is not None else (review_until if review_until is not None else DEFAULT_REVIEW_UNTIL))
        self.review_until = min(max(ru, self.threshold), 1.0)      # nunca abaixo do limiar

    @classmethod
    def load(cls, model_dir: str | Path, input_size: int = 0, review_until: float | None = None) -> "ServerModel":
        d = Path(model_dir)
        missing = [n for n in ("model.onnx", "labels.json", "model_card.json") if not (d / n).is_file()]
        if missing:
            raise ServerModelUnavailable(f"faltam em {d}: {', '.join(missing)}")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ServerModelUnavailable("onnxruntime não está instalado (pip install onnxruntime)") from exc
        try:
            card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
            if not isinstance(card, dict):
                raise ValueError("model_card.json não é um objeto JSON")
            labels = map_classes(json.loads((d / "labels.json").read_text(encoding="utf-8")), card)
        except (ValueError, TypeError) as exc:
            raise ServerModelUnavailable(f"labels.json ou model_card.json inválido: {exc}") from exc
        try:
            session = ort.InferenceSession(str(d / "model.onnx"), providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise ServerModelUnavailable(f"não consegui abrir o ONNX: {type(exc).__name__}: {exc}") from exc
        out_dim = session.get_outputs()[0].shape[-1]
        if isinstance(out_dim, int) and out_dim != 2:
            raise ServerModelUnavailable(f"o modelo tem {out_dim} saídas; o sistema é binário (2: não precisa limpar / precisa limpar)")
        try:
            return cls(session, card, labels, input_size, review_until)
        except (ValueError, TypeError) as exc:
            raise ServerModelUnavailable(f"model_card.json inválido: {exc}") from exc

    def preprocess(self, img: Image.Image) -> np.ndarray:
        """Estica para size×size (sem recorte), RGB. Faixa e layout seguem o card/ONNX."""
        arr = np.asarray(img.convert("RGB").resize((self.size, self.size), Image.BILINEAR), dtype=np.float32)
        if not self.raw_0_255:
            arr = (arr / 255.0 - self.mean) / self.std
        x = arr if self.nhwc else arr.transpose(2, 0, 1)
        return x[None].astype(np.float32)

    def decide(self, p_positive: float) -> tuple[Label, float, bool]:
        """(classe, confiança da classe escolhida, faixa de dúvida?)."""
        if p_positive >= self.threshold:
            return Label.SEVERO, p_positive, p_positive < self.review_until
        return Label.LIMPO, 1.0 - p_positive, False

    def predict(self, img: Image.Image) -> ServerPrediction:
        t0 = time.perf_counter()
        out = np.asarray(self.session.run(None, {self.input_name: self.preprocess(img)})[0], dtype=np.float32)
        p = (out if self.outputs_probs else softmax(out))[0]
        p_pos = float(np.clip(p[self.positive], 0.0, 1.0))
        label, conf, doubt = self.decide(p_pos)
        return ServerPrediction(label, conf, p_pos, doubt, {Label.LIMPO.value: 1.0 - p_pos, Label.SEVERO.value: p_pos},
                                (time.perf_counter() - t0) * 1000, self.version)

    def info(self) -> dict:
        return {"version": self.version, "input_size": self.size, "classes": [l.value for l in (Label.LIMPO, Label.SEVERO)],
                "limiar": self.threshold, "revisao_ate": self.review_until}


def _layout(shape, card: dict) -> str:
    declared = str(_get(card, "onnx", "input", "layout") or card.get("layout") or "").upper()
    if declared in {"NHWC", "NCHW"}:
        return declared
    return "NHWC" if len(shape) == 4 and shape[-1] == 3 else "NCHW"


def _fixed_side(shape, nhwc: bool) -> int | None:
    if len(shape) != 4:
        return None
    side = shape[1] if nhwc else shape[2]
    return side if isinstance(side, int) else None


def try_load(model_dir: str, input_size: int = 0, review_until: float | None = None) -> tuple[ServerModel | None, str | None]:
    """Carrega se existir; devolve (modelo, motivo_da_indisponibilidade). Nunca levanta: o servidor sobe sem o modelo grande."""
    try:
        return ServerModel.load(model_dir, input_size, review_until), None
    except ServerModelUnavailable as exc:
        return None, str(exc)
