Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = "tools"
# O simulador usa o MESMO modelo gravado no ESP32 (models/esp32/model.tflite, soilnet 2x, 112 px, LIMPO/SEVERO).
# Só se ele faltar cai no modelo sintético de demonstração (96 px, decide pela cor; NÃO classifica sujeira).
if (Test-Path "models/esp32/model.tflite") {
  Write-Host ">> Modelo do ESP32 (models/esp32)"
  $simArgs = "-m","esp32_simulator.server","--model-dir","models/esp32","--port","8081","--host","127.0.0.1"
  $size = "112"; $classes = "LIMPO,SEVERO"
} else {
  Write-Host ">> Sem modelo em models/esp32: usando o modelo SINTETICO de demonstracao"
  $simArgs = "-m","esp32_simulator.server","--demo-model","--port","8081","--host","127.0.0.1"
  $size = "96"; $classes = "LIMPO,SEVERO"
}
$sim = Start-Process -PassThru -NoNewWindow .\.venv\Scripts\python -ArgumentList $simArgs
try {
  Set-Location backend
  if (-not $env:SERVER_MODEL_DIR) { $env:SERVER_MODEL_DIR = (Resolve-Path "..\models\server").Path }
  $env:ESP32_URL = "http://127.0.0.1:8081"; $env:ESP32_INPUT_SIZE = $size; $env:ESP32_CLASSES = $classes
  ..\.venv\Scripts\python -m uvicorn main:app --port 8000
} finally { Stop-Process -Id $sim.Id -ErrorAction SilentlyContinue }
