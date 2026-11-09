"""Rótulos do projeto: LIMPO, MODERADO, SEVERO. É só isso: não existe perda de potência, valor em R$ nem regressão.

A ordem de LABELS é a ordem das saídas do modelo e é gravada no model_card.json. Nunca reordene sem retreinar.
"""
from __future__ import annotations

from enum import Enum


class Label(str, Enum):
    LIMPO = "LIMPO"
    MODERADO = "MODERADO"
    SEVERO = "SEVERO"


LABELS: tuple[Label, ...] = (Label.LIMPO, Label.MODERADO, Label.SEVERO)
SEVERITY: dict[Label, int] = {Label.LIMPO: 0, Label.MODERADO: 1, Label.SEVERO: 2}

# Nomes de classe que aparecem em datasets -> nosso rótulo.
# Dataset Roboflow "solar-panel-dust-and-soiling": Clean, Dusty, Soiled.
# ATENÇÃO: Clean=LIMPO, Dusty=MODERADO, Soiled=SEVERO é uma SUPOSIÇÃO da equipe, não vem do dataset.
# Confirme olhando exemplos de cada classe (docs/02_DATASET_E_TREINO.md) e ajuste com --class-map.
DEFAULT_CLASS_MAP: dict[str, Label] = {
    "clean": Label.LIMPO, "limpo": Label.LIMPO,
    "dusty": Label.MODERADO, "moderado": Label.MODERADO, "moderate": Label.MODERADO,
    "soiled": Label.SEVERO, "severo": Label.SEVERO, "severe": Label.SEVERO,
}


class UnknownClassError(ValueError):
    pass


def normalize_label(name: str, class_map: dict[str, Label] | None = None) -> Label:
    key = name.strip().lower()
    mapping = class_map if class_map is not None else DEFAULT_CLASS_MAP
    if key not in mapping:
        raise UnknownClassError(f"classe desconhecida: {name!r}. Conhecidas: {sorted(mapping)}. Use --class-map para mapear.")
    return mapping[key]


def parse_class_map(text: str) -> dict[str, Label]:
    """'Dusty=MODERADO,Soiled=SEVERO' -> mapa (somado ao padrão)."""
    out = dict(DEFAULT_CLASS_MAP)
    for part in filter(None, (p.strip() for p in text.split(","))):
        src, _, dst = part.partition("=")
        out[src.strip().lower()] = Label(dst.strip().upper())
    return out


def suggested_action(label: Label, low_confidence: bool) -> str:
    """Ação sugerida ao operador. Baixa confiança sempre pede revisão humana primeiro."""
    if low_confidence:
        return "revisar"
    return {Label.LIMPO: "nenhuma", Label.MODERADO: "agendar_limpeza", Label.SEVERO: "acionar_limpeza"}[label]
