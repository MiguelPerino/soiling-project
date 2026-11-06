"""Configuração por variáveis de ambiente (ver .env.example). Nenhum segredo no código."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./data/app.db"
    storage_dir: str = "./storage/images"       # imagens ficam em arquivos; o banco guarda só o caminho relativo
    esp32_url: str = ""                          # ex.: http://192.168.0.50 (vazio = ESP32 não configurado)
    esp32_key: str = ""                          # segredo compartilhado opcional (cabeçalho X-Device-Key)
    esp32_timeout_s: float = 30.0
    input_size: int = 96                         # lado da imagem que o modelo do ESP32 espera (ai-model/models/current/model_card.json)
    jpeg_quality: int = 85
    low_confidence_threshold: float = 0.60
    admin_api_key: str = ""                      # vazio = sem proteção (só desenvolvimento local)
    gemini_api_key: str = ""
    gemini_model: str = ""                       # sem padrão de propósito: nomes de modelo mudam; defina no .env
    max_upload_mb: int = 10
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    frontend_dir: str = ""                       # pasta do build do front (frontend/dist); vazio = não serve front

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_model)

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ
        default_front = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        return cls(
            database_url=e.get("DATABASE_URL", cls.database_url),
            storage_dir=e.get("STORAGE_DIR", cls.storage_dir),
            esp32_url=e.get("ESP32_URL", "").rstrip("/"),
            esp32_key=e.get("ESP32_KEY", ""),
            esp32_timeout_s=float(e.get("ESP32_TIMEOUT_S", "30")),
            input_size=int(e.get("INPUT_SIZE", "96")),
            jpeg_quality=int(e.get("JPEG_QUALITY", "85")),
            low_confidence_threshold=float(e.get("LOW_CONFIDENCE_THRESHOLD", "0.60")),
            admin_api_key=e.get("ADMIN_API_KEY", ""),
            gemini_api_key=e.get("GEMINI_API_KEY", ""),
            gemini_model=e.get("GEMINI_MODEL", ""),
            max_upload_mb=int(e.get("MAX_UPLOAD_MB", "10")),
            cors_origins=tuple(o.strip() for o in e.get("CORS_ORIGINS", "").split(",") if o.strip()),
            frontend_dir=e.get("FRONTEND_DIR", str(default_front) if default_front.is_dir() else ""),
        )
