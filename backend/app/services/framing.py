"""Enquadramento das fotos para o modelo grande: cópia FIEL do `preprocess.py` gerado pelo notebook
`tratamento_dataset_224.ipynb` do time (célula 3, "Funções de tratamento"). O ResNet foi treinado com fotos que passaram
por aqui, então a inferência tem que passar pelo MESMO código. Não "melhore" a lógica sem retreinar o modelo.

O que faz em cada foto (RGB, orientação EXIF já corrigida pelo backend):
  1. remove faixas uniformes nas bordas (barras pretas/brancas);
  2. acha a placa pela cor (azul ou cinza/preta) e recorta um quadrado em volta dela, com folga (FRAME_MARGIN);
     se não achar, recorte quadrado central (CENTER_FRAC do lado menor);
  3. se a região for alongada demais (> WIDE_RATIO), completa o quadrado com um fundo desfocado da própria foto;
  4. redimensiona para size×size (INTER_AREA ao reduzir, INTER_CUBIC ao ampliar).
Nenhuma mudança de cor, brilho ou contraste.

Diferenças em relação ao notebook (só de entrada/saída, não de lógica): recebe o array RGB em vez do caminho do arquivo
(o backend já abriu e corrigiu a orientação), e os parâmetros vêm do model_card.json quando ele os tiver.
"""
from __future__ import annotations

import cv2
import numpy as np

# Valores da célula 1 (CFG) do notebook que gerou o dataset do resnet50-224-20261116.
IMG_SIZE = 224
FRAMING = "panel"
FRAME_MARGIN = 0.06
CENTER_FRAC = 0.90
WIDE_RATIO = 1.5
MODES = ("panel", "center", "none")


def trim_borders(img, tol=6.0, max_cut=0.2):
    # remove linhas/colunas uniformes nas bordas (barras de letterbox), até max_cut de cada lado
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = g.shape
    top, bottom, left, right = 0, h, 0, w
    while top < h * max_cut and g[top].std() < tol:
        top += 1
    while h - bottom < h * max_cut and g[bottom - 1].std() < tol:
        bottom -= 1
    while left < w * max_cut and g[:, left].std() < tol:
        left += 1
    while w - right < w * max_cut and g[:, right - 1].std() < tol:
        right -= 1
    return img[top:bottom, left:right]


def detect_panel_box(img, work=256, min_frac=0.12, max_frac=0.98, min_fill=0.35):
    # caixa (x0, y0, x1, y1) da placa pela cor; None se não encontrar ou se a detecção parecer duvidosa
    h, w = img.shape[:2]
    s = work / max(h, w)
    small = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV).astype(np.int32)
    H, Sat, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    azul = (H >= 85) & (H <= 135) & (Sat >= 30) & (V >= 25)          # placas azuis (policristalinas / vidro)
    cinza = (Sat <= 40) & (V >= 55) & (V <= 190)                      # placas pretas/cinza (com reflexo ou poeira)
    mask = ((azul | cinza).astype(np.uint8)) * 255
    k = max(3, work // 40)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return None, 0.0
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = [i + 1 for i, a in enumerate(areas) if a >= 0.15 * areas.max()]
    x0 = min(stats[i, cv2.CC_STAT_LEFT] for i in keep)
    y0 = min(stats[i, cv2.CC_STAT_TOP] for i in keep)
    x1 = max(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] for i in keep)
    y1 = max(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] for i in keep)
    frac = (x1 - x0) * (y1 - y0) / float(small.shape[0] * small.shape[1])
    if frac < min_frac or (mask[y0:y1, x0:x1] > 0).mean() < min_fill:
        return None, frac
    if frac > max_frac:                                               # a placa já ocupa a foto inteira
        return (0, 0, w, h), frac
    return (int(x0 / s), int(y0 / s), int(np.ceil(x1 / s)), int(np.ceil(y1 / s))), frac


def _clamp(a0, a1, lim):
    if a1 - a0 >= lim:
        return 0.0, float(lim)
    if a0 < 0:
        a1 -= a0; a0 = 0.0
    if a1 > lim:
        a0 -= a1 - lim; a1 = float(lim)
    return a0, a1


def blur_fill(part):
    # completa até quadrado com a PRÓPRIA imagem esticada e bem desfocada ao fundo (sem branco, sem duplicar a placa)
    ph, pw = part.shape[:2]
    side = max(ph, pw)
    bg = cv2.resize(part, (side, side), interpolation=cv2.INTER_AREA)
    k = max(3, (side // 8) | 1)
    bg = cv2.GaussianBlur(bg, (k, k), 0)
    y0, x0 = (side - ph) // 2, (side - pw) // 2
    bg[y0:y0 + ph, x0:x0 + pw] = part
    return bg


def square_region(img, box, margin, wide_ratio):
    # devolve (região quadrada, como foi feita). Recorta um quadrado em volta da caixa. Se a caixa for
    # alongada demais para caber num quadrado dentro da foto, usa a maior região real possível em volta dela
    # e completa o que faltar com um fundo desfocado da própria imagem (nada é cortado da placa).
    h, w = img.shape[:2]
    x0, y0, x1, y1 = [float(v) for v in box]
    bw, bh = x1 - x0, y1 - y0
    x0 -= bw * margin; x1 += bw * margin; y0 -= bh * margin; y1 += bh * margin
    x0, x1 = _clamp(x0, x1, w); y0, y1 = _clamp(y0, y1, h)
    bw, bh = x1 - x0, y1 - y0
    side = max(bw, bh)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if max(bw, bh) / max(min(bw, bh), 1) > wide_ratio and side > min(w, h):
        if bw >= bh:                                   # larga: estende para cima/baixo com conteúdo real
            y0, y1 = _clamp(cy - side / 2, cy + side / 2, h)
        else:                                          # alta: estende para os lados
            x0, x1 = _clamp(cx - side / 2, cx + side / 2, w)
        part = img[int(y0):int(round(y1)), int(x0):int(round(x1))]
        if part.shape[0] == part.shape[1]:
            return part, "recorte"
        return blur_fill(part), "fundo_desfocado"
    side = min(side, w, h)
    sx0, sx1 = _clamp(cx - side / 2, cx + side / 2, w)
    sy0, sy1 = _clamp(cy - side / 2, cy + side / 2, h)
    return img[int(sy0):int(round(sy1)), int(sx0):int(round(sx1))], "recorte"


def frame_image(img, size=IMG_SIZE, mode=FRAMING, margin=FRAME_MARGIN, center_frac=CENTER_FRAC, wide_ratio=WIDE_RATIO):
    # imagem RGB -> (imagem RGB size x size uint8, info). Use a MESMA função no treino e na inferência.
    img = trim_borders(img)
    h, w = img.shape[:2]
    info = {"deteccao": None, "frac_placa": None}
    box = None
    if mode == "panel":
        box, frac = detect_panel_box(img)
        info["frac_placa"] = round(float(frac), 3)
        info["deteccao"] = "placa" if box is not None else "nao_encontrada"
    if box is None:                                                   # recorte central (ou foto inteira, se for larga)
        if max(w, h) / min(w, h) > wide_ratio:
            box, margin = (0, 0, w, h), 0.0
        else:
            side = min(w, h) * center_frac
            box, margin = ((w - side) / 2, (h - side) / 2, (w + side) / 2, (h + side) / 2), 0.0
    part, how = square_region(img, box, margin, wide_ratio)
    info["metodo"] = ("placa" if info["deteccao"] == "placa" else "central") + "+" + how
    interp = cv2.INTER_AREA if max(part.shape[:2]) > size else cv2.INTER_CUBIC
    return cv2.resize(part, (size, size), interpolation=interp), info
