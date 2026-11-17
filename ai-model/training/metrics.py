"""Métricas de classificação BINÁRIA em numpy puro (sem torch, sem sklearn): rodam em qualquer ambiente e nos testes.

A decisão é por LIMIAR na classe positiva (LIMPAR -> SEVERO), igual ao firmware (decision.h) e ao simulador:
P(positiva) >= limiar => positiva. Não é o argmax.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from labels import LABELS, POSITIVE


def predict(p_pos: Sequence[float], threshold: float) -> np.ndarray:
    """Índice previsto (0 = LIMPO, 1 = SEVERO) pela regra do firmware."""
    return np.where(np.asarray(p_pos, dtype=float) >= threshold, POSITIVE, 1 - POSITIVE)


def confusion_matrix(y_true: Sequence[int], y_pred: Sequence[int], n: int = len(LABELS)) -> np.ndarray:
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[int(t), int(p)] += 1
    return cm


def per_class(cm: np.ndarray) -> list[dict]:
    out = []
    for i, label in enumerate(LABELS[: cm.shape[0]]):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out.append({"classe": label, "precisao": precision, "recall": recall, "f1": f1, "suporte": int(cm[i, :].sum())})
    return out


def summarize(y_true: Sequence[int], y_pred: Sequence[int]) -> dict:
    cm = confusion_matrix(y_true, y_pred)
    classes = per_class(cm)
    total = int(cm.sum())
    neg = 1 - POSITIVE
    n_neg, n_pos = int(cm[neg].sum()), int(cm[POSITIVE].sum())
    return {
        "n": total,
        "acuracia": float(np.trace(cm) / total) if total else 0.0,
        "acuracia_balanceada": float(np.mean([c["recall"] for c in classes])) if classes else 0.0,
        "f1_macro": float(np.mean([c["f1"] for c in classes])) if classes else 0.0,
        "por_classe": classes,
        "matriz_confusao": cm.tolist(),
        "ordem_classes": list(LABELS),
        # os dois erros que importam para a bomba
        "limpos_que_acionariam_pct": float(cm[neg, POSITIVE] / n_neg) if n_neg else 0.0,
        "sujos_ignorados_pct": float(cm[POSITIVE, neg] / n_pos) if n_pos else 0.0,
    }


def auc(y_true: Sequence[int], p_pos: Sequence[float]) -> float | None:
    """AUC-ROC pela estatística de Mann-Whitney (empates contam meio). None se só houver uma classe."""
    y, s = np.asarray(y_true) == POSITIVE, np.asarray(p_pos, dtype=float)
    pos, neg = s[y], s[~y]
    if not len(pos) or not len(neg):
        return None
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def choose_threshold(y_true: Sequence[int], p_pos: Sequence[float], grid: Sequence[float] | None = None) -> dict:
    """Limiar de operação escolhido na VALIDAÇÃO pelo maior F1 macro (empate: o mais perto de 0,5).
    É o "limiar_limpar" do model_card.json e o DECISION_THRESHOLD do firmware."""
    grid = np.round(np.arange(0.05, 0.951, 0.01), 2) if grid is None else np.asarray(grid, dtype=float)
    best = None
    for t in grid:
        f1 = summarize(y_true, predict(p_pos, float(t)))["f1_macro"]
        key = (round(f1, 6), -abs(float(t) - 0.5))
        if best is None or key > best[0]:
            best = (key, float(t), f1)
    return {"limiar": best[1], "f1_macro_validacao": best[2], "criterio": "f1_macro"}


def selective(p_pos: Sequence[float], y_true: Sequence[int], decision: float, pump: float) -> dict:
    """Regra da bomba: só SEVERO com confiança (= P(positiva)) >= `pump` aciona. Quantos sujos ela pega e quantos limpos ela molha."""
    p, y = np.asarray(p_pos, dtype=float), np.asarray(y_true)
    fires = (p >= decision) & (p >= pump)
    n_pos, n_neg = int((y == POSITIVE).sum()), int((y != POSITIVE).sum())
    return {
        "limiar_decisao": decision, "limiar_bomba": pump,
        "sujos_que_acionam_pct": float(fires[y == POSITIVE].mean()) if n_pos else 0.0,
        "limpos_que_acionam_pct": float(fires[y != POSITIVE].mean()) if n_neg else 0.0,
    }
