#!/usr/bin/env bash
# Sobe o simulador do ESP32 e a API com SQLite, sem Docker e sem hardware. http://localhost:8000
# Se existir ai-model/models/current/model.tflite (soilnet v1), o simulador usa ESSE modelo (112 px, LIMPO/SEVERO).
# Senão usa o modelo sintético de demonstração (96 px, decide pela cor; NÃO classifica sujeira).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
export PYTHONPATH=tools
if [ -f ai-model/models/current/model.tflite ]; then
  echo ">> Modelo REAL do time: $(grep -o '"version": "[^"]*"' ai-model/models/current/model_card.json)"
  "$ROOT/.venv/bin/python" -m esp32_simulator.server --model-dir ai-model/models/current --port 8081 --host 127.0.0.1 &
  SIZE=112; CLASSES=LIMPO,SEVERO
else
  echo ">> Sem modelo em ai-model/models/current: usando o modelo SINTÉTICO de demonstração"
  "$ROOT/.venv/bin/python" -m esp32_simulator.server --demo-model --port 8081 --host 127.0.0.1 &
  SIZE=96; CLASSES=LIMPO,SEVERO
fi
SIM=$!; trap 'kill $SIM' EXIT
cd backend
SERVER_MODEL_DIR="${SERVER_MODEL_DIR:-$ROOT/models/server}" ESP32_URL=http://127.0.0.1:8081 ESP32_INPUT_SIZE=$SIZE ESP32_CLASSES=$CLASSES "$ROOT/.venv/bin/python" -m uvicorn main:app --port 8000
