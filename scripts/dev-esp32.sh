#!/usr/bin/env bash
# Sobe SÓ a API (SQLite) falando com o ESP32 de verdade. Uso: scripts/dev-esp32.sh 192.168.0.50   (IP que o ESP32 imprime no monitor serial)
# Notebook e ESP32 precisam estar na MESMA rede Wi-Fi. Abra http://localhost:8000
set -euo pipefail
[ $# -ge 1 ] || { echo "uso: $0 <IP-do-ESP32>"; exit 1; }
cd "$(dirname "$0")/../backend"
ROOT="$(cd .. && pwd)"
SERVER_MODEL_DIR="${SERVER_MODEL_DIR:-$ROOT/models/server}" ESP32_URL="http://$1" ESP32_INPUT_SIZE=112 ESP32_CLASSES=LIMPO,SEVERO ESP32_KEY="${ESP32_KEY:-}" exec "$ROOT/.venv/bin/python" -m uvicorn main:app --port 8000
