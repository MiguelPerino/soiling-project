#!/usr/bin/env bash
# Sobe o simulador do ESP32 e a API com SQLite, sem Docker e sem hardware. http://localhost:8000
# O simulador usa o MESMO modelo gravado no ESP32 (models/esp32/model.tflite, soilnet 2x, 112 px, LIMPO/SEVERO).
# Só se ele faltar cai no modelo sintético de demonstração (96 px, decide pela cor; NÃO classifica sujeira).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PYTHONPATH=tools
if [ -f models/esp32/model.tflite ]; then
  echo ">> Modelo do ESP32: $(grep -o '"version": "[^"]*"' models/esp32/model_card.json)"
  "$ROOT/.venv/bin/python" -m esp32_simulator.server --model-dir models/esp32 --port 8081 --host 127.0.0.1 &
  SIZE=112; CLASSES=LIMPO,SEVERO
else
  echo ">> Sem modelo em models/esp32: usando o modelo SINTÉTICO de demonstração"
  "$ROOT/.venv/bin/python" -m esp32_simulator.server --demo-model --port 8081 --host 127.0.0.1 &
  SIZE=96; CLASSES=LIMPO,SEVERO
fi
SIM=$!; trap 'kill $SIM' EXIT
cd backend
SERVER_MODEL_DIR="${SERVER_MODEL_DIR:-$ROOT/models/server}" ESP32_URL=http://127.0.0.1:8081 ESP32_INPUT_SIZE=$SIZE ESP32_CLASSES=$CLASSES "$ROOT/.venv/bin/python" -m uvicorn main:app --port 8000
