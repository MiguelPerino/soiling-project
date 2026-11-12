Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = "tools"
# Se existir ai-model/models/current/model.tflite (soilnet v1), o simulador usa ESSE modelo (112 px, LIMPO/SEVERO).
# Senão usa o modelo sintético de demonstração (96 px, decide pela cor; NÃO classifica sujeira).
if (Test-Path "ai-model/models/current/model.tflite") {
  Write-Host ">> Modelo REAL do time (ai-model/models/current)"
  $simArgs = "-m","esp32_simulator.server","--model-dir","ai-model/models/current","--port","8081","--host","127.0.0.1"
  $size = "112"; $classes = "LIMPO,SEVERO"
} else {
  Write-Host ">> Sem modelo em ai-model/models/current: usando o modelo SINTETICO de demonstracao"
  $simArgs = "-m","esp32_simulator.server","--demo-model","--port","8081","--host","127.0.0.1"
  $size = "96"; $classes = "LIMPO,MODERADO,SEVERO"
}
$sim = Start-Process -PassThru -NoNewWindow .\.venv\Scripts\python -ArgumentList $simArgs
try {
  Set-Location backend
  $env:ESP32_URL = "http://127.0.0.1:8081"; $env:ESP32_INPUT_SIZE = $size; $env:ESP32_CLASSES = $classes
  ..\.venv\Scripts\python -m uvicorn main:app --port 8000
} finally { Stop-Process -Id $sim.Id -ErrorAction SilentlyContinue }
