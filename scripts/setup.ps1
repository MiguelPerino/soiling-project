# Prepara o ambiente de desenvolvimento no Windows (PowerShell).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r backend\requirements-dev.txt
Push-Location frontend; npm ci --no-audit --no-fund; npm run build; Pop-Location
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
try { & .\scripts\download-model.ps1 } catch { $_ | Out-Null }
if ($LASTEXITCODE -ne 0) { Write-Host "AVISO: o modelo grande não foi baixado. O modo Servidor fica indisponível até rodar scripts\download-model.ps1." }
Write-Host "Pronto. Testes: scripts\test.ps1 | Rodar: scripts\dev.ps1"
