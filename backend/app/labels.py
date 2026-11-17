"""Rótulos do projeto: duas classes, LIMPO ("Não precisa limpar") e SEVERO ("Precisa limpar").

Os CÓDIGOS (LIMPO, SEVERO) são o que vai no banco, na API e no protocolo do ESP32; os TEXTOS (LABEL_TEXT) são o que a tela
mostra. O modelo não mede quanto de sujeira há: ele só diz se o painel precisa ou não de limpeza.

Cada modelo traz os próprios nomes de classe (o do servidor usa NaoLimpar/Limpar no labels.json) e o backend os traduz
para estes códigos. A ordem das classes de cada modelo é a ordem das suas saídas e fica no labels.json/model_card.json.
"""
from __future__ import annotations

from enum import Enum


class Label(str, Enum):
    LIMPO = "LIMPO"        # não precisa limpar
    SEVERO = "SEVERO"      # precisa limpar (a bomba do ESP32 só age nesta classe)


LABELS: tuple[Label, ...] = (Label.LIMPO, Label.SEVERO)
LABEL_TEXT: dict[Label, str] = {Label.LIMPO: "Não precisa limpar", Label.SEVERO: "Precisa limpar"}


class UnknownClassError(ValueError):
    pass


def parse_classes(text: str | list[str] | tuple[str, ...]) -> tuple[Label, ...]:
    """'LIMPO,SEVERO' -> (LIMPO, SEVERO). Valida e mantém a ordem (= ordem das saídas do modelo).

    Usado para as classes do ESP32 (ESP32_CLASSES). Regras: nomes conhecidos, sem repetição, exatamente LIMPO e SEVERO.
    """
    parts = [p.strip().upper() for p in (text.split(",") if isinstance(text, str) else text) if str(p).strip()]
    try:
        out = tuple(Label(p) for p in parts)
    except ValueError as exc:
        raise UnknownClassError(f"classe inválida em {parts}; use apenas {[l.value for l in LABELS]}") from exc
    if len(set(out)) != len(out):
        raise UnknownClassError(f"classes repetidas: {parts}")
    if set(out) != set(LABELS):
        raise UnknownClassError(f"as classes precisam ser LIMPO e SEVERO (recebi {parts})")
    return out


def suggested_action(label: Label, low_confidence: bool) -> str:
    """Ação sugerida ao operador. Baixa confiança (ou faixa de dúvida) sempre pede revisão humana primeiro."""
    if low_confidence:
        return "revisar"
    return {Label.LIMPO: "nenhuma", Label.SEVERO: "acionar_limpeza"}[label]
