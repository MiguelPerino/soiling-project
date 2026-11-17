"""Rótulos do modelo do ESP32: BINÁRIO, igual ao resto do sistema (backend/app/labels.py).

Dois nomes para as mesmas duas classes, na ordem das saídas do modelo:
    índice 0   LIMPO    (no modelo: NAOLIMPAR)  "Não precisa limpar"
    índice 1   SEVERO   (no modelo: LIMPAR)     "Precisa limpar"  <- classe positiva: a única que pode acionar a bomba
O labels.json e o model_card.json exportados usam os nomes do MODELO (NAOLIMPAR/LIMPAR + positive_label), o mesmo formato do
soilnet v1 que o firmware (config.h: CLASS_NAMES, POSITIVE_CLASS=1) e o simulador (tflite_engine.py) já leem.
"""
LABELS = ("LIMPO", "SEVERO")                 # códigos do sistema, na ordem das saídas
MODEL_NAMES = ("NAOLIMPAR", "LIMPAR")        # nomes no labels.json exportado (mesma ordem)
POSITIVE = 1                                 # índice da classe positiva (LIMPAR -> SEVERO)

# Nome de pasta/coluna do dataset -> código do sistema. Pastas do notebook do time (Limpar/NaoLimpar), do export do
# backend (LIMPO/SEVERO) e do Roboflow "solar-panel-dust-and-soiling" (Clean/Soiled).
# "Dusty" (poeira) NÃO tem padrão de propósito: no sistema binário é preciso decidir se poeira já "precisa limpar".
# Olhe exemplos e passe --class-map "Dusty=SEVERO" (ou "Dusty=LIMPO").
DEFAULT_CLASS_MAP = {
    "limpo": "LIMPO", "naolimpar": "LIMPO", "nao_limpar": "LIMPO", "nao limpar": "LIMPO", "clean": "LIMPO",
    "severo": "SEVERO", "limpar": "SEVERO", "soiled": "SEVERO", "sujo": "SEVERO", "dirty": "SEVERO", "severe": "SEVERO",
}


def parse_class_map(text: str | None) -> dict[str, str]:
    out = dict(DEFAULT_CLASS_MAP)
    for part in filter(None, (p.strip() for p in (text or "").split(","))):
        src, _, dst = part.partition("=")
        if dst.strip().upper() not in LABELS:
            raise ValueError(f"destino inválido em --class-map: {part!r}; use {LABELS}")
        out[src.strip().lower()] = dst.strip().upper()
    return out


def to_label(name: str, class_map: dict[str, str]) -> str:
    key = name.strip().lower()
    if key not in class_map:
        hint = ' (poeira: decida se já "precisa limpar" e passe --class-map "Dusty=SEVERO" ou "Dusty=LIMPO")' if "dust" in key or "moder" in key else ""
        raise ValueError(f"classe desconhecida: {name!r}{hint}. Conhecidas: {sorted(class_map)}. Use --class-map.")
    return class_map[key]
