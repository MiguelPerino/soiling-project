# Sobe SÓ a API (SQLite) falando com o ESP32 de verdade. Uso: .\scripts\dev-esp32.ps1 192.168.0.50   (IP que o ESP32 imprime no monitor serial)
# Notebook e ESP32 precisam estar na MESMA rede Wi-Fi. Abra http://localhost:8000
param([Parameter(Mandatory=$true)][string]$Ip)
Set-Location (Join-Path $PSScriptRoot "..\backend")
if (-not $env:SERVER_MODEL_DIR) { $env:SERVER_MODEL_DIR = (Resolve-Path (Join-Path $PSScriptRoot "..\models\server")).Path }
$env:ESP32_URL = "http://$Ip"; $env:ESP32_INPUT_SIZE = "112"; $env:ESP32_CLASSES = "LIMPO,SEVERO"
..\.venv\Scripts\python -m uvicorn main:app --port 8000
