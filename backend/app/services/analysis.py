"""Fluxo de uma análise: prepara a imagem -> ESP32 classifica e decide a bomba -> grava arquivo + linha no banco.

O backend NÃO executa o modelo. Só encaminha e registra o que o ESP32 devolveu.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

from app.database.repository import Repository
from app.services.esp32 import Esp32Client
from app.services.storage import ImageStore

MAX_PIXELS = 50_000_000


class InvalidImage(ValueError):
    pass


def prepare_image(data: bytes, size: int, quality: int = 85) -> tuple[bytes, int, int]:
    """Devolve JPEG size×size (estica, igual ao treino). Se já vier assim do front, não recodifica."""
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        probe = Image.open(BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            raise InvalidImage("imagem grande demais")
        if fmt not in {"JPEG", "PNG", "WEBP"}:
            raise InvalidImage(f"formato {fmt} não suportado; envie JPEG, PNG ou WEBP")
        if fmt == "JPEG" and (img.width, img.height) == (size, size) and not img.getexif().get(274):
            return data, size, size
        img = ImageOps.exif_transpose(img).convert("RGB").resize((size, size), Image.BILINEAR)
    except InvalidImage:
        raise
    except Exception as exc:
        raise InvalidImage(f"arquivo não é uma imagem válida ({type(exc).__name__})") from exc
    buf = BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue(), size, size


def analyze(data: bytes, filename: str, *, size: int, quality: int, low_conf: float, pump: bool,
            esp32: Esp32Client, store: ImageStore, repo: Repository) -> dict:
    jpeg, w, h = prepare_image(data, size, quality)
    result, round_trip_ms = esp32.upload(jpeg, pump)           # falhou? nada é gravado
    rel = store.save(jpeg)
    try:
        row = repo.add(
            image_path=rel, original_filename=(filename or "foto")[:255], classification=result.classification.value,
            confidence=result.confidence, probs=result.probs, low_confidence=result.confidence < low_conf,
            cleaning_activated=result.cleaning_activated, pump_duration_ms=result.pump_duration_ms,
            pump_reason=result.reason, dirt_level=result.dirt_level, model_version=result.model_version,
            inference_ms=result.inference_ms, round_trip_ms=round_trip_ms, width=w, height=h,
        )
    except Exception:
        store.delete(rel)                                       # sem arquivo órfão
        raise
    return row
