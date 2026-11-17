# Baixa o modelo grande (modo Servidor) da release do GitHub indicada em models/server/model.lock e confere o SHA-256.
# O repositório é privado, então o download precisa de login:
#   - GitHub CLI logado (gh auth login), ou
#   - $env:GITHUB_TOKEN com permissão de leitura do repositório.
# Uso: scripts\download-model.ps1           baixa (se os arquivos da pasta não forem os esperados)
#      scripts\download-model.ps1 -Check    só confere o que já está em models\server\
param([switch]$Check)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$dir = "models/server"
$lock = Get-Content "$dir/model.lock" | Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() }
$repo = ($lock | Where-Object { $_ -match '^repo ' }) -replace '^repo\s+', ''
$tag = ($lock | Where-Object { $_ -match '^tag ' }) -replace '^tag\s+', ''
$hashes = @{}
foreach ($l in ($lock | Where-Object { $_ -match '^sha256 ' })) { $p = $l -split '\s+'; $hashes[$p[2]] = $p[1].ToLower() }
$page = "https://github.com/$repo/releases/tag/$tag"

function Test-Model([string]$folder) {
  $ok = $true
  foreach ($f in $hashes.Keys) {
    $path = Join-Path $folder $f
    if (-not (Test-Path $path)) { Write-Host "  falta: $f"; $ok = $false }
    elseif ((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -ne $hashes[$f]) { Write-Host "  SHA-256 diferente do esperado: $f"; $ok = $false }
  }
  return $ok
}

if (Test-Model $dir 6>$null) { Write-Host "Modelo $tag já está em $dir (SHA-256 conferido)."; exit 0 }
if ($Check) {
  Write-Host "O modelo em $dir não é o esperado ($tag):"; Test-Model $dir | Out-Null
  Write-Host "Baixe com: scripts\download-model.ps1"; exit 1
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid())
New-Item -ItemType Directory $tmp | Out-Null
try {
  Write-Host "Baixando $tag de $repo ..."
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if ($gh) { & gh auth status *> $null; $ghOk = ($LASTEXITCODE -eq 0) } else { $ghOk = $false }
  if ($ghOk) {
    $pats = @(); foreach ($f in $hashes.Keys) { $pats += @("-p", $f) }
    & gh release download $tag -R $repo -D $tmp @pats
    if ($LASTEXITCODE -ne 0) { throw "gh release download falhou" }
  } elseif ($env:GITHUB_TOKEN) {
    $h = @{ Authorization = "Bearer $env:GITHUB_TOKEN" }
    $rel = Invoke-RestMethod -Headers $h "https://api.github.com/repos/$repo/releases/tags/$tag"
    foreach ($f in $hashes.Keys) {
      $id = ($rel.assets | Where-Object { $_.name -eq $f }).id
      Invoke-WebRequest -Headers ($h + @{ Accept = "application/octet-stream" }) -OutFile (Join-Path $tmp $f) "https://api.github.com/repos/$repo/releases/assets/$id"
    }
  } else {
    Write-Host "Sem login no GitHub (o repositório é privado). Escolha uma opção:"
    Write-Host "  1) instale o GitHub CLI (https://cli.github.com), rode 'gh auth login' e rode este script de novo; ou"
    Write-Host "  2) defina `$env:GITHUB_TOKEN com permissão de leitura do repositório e rode de novo; ou"
    Write-Host "  3) baixe à mão os arquivos ($($hashes.Keys -join ', ')) em $page,"
    Write-Host "     coloque em $dir\ e confira com: scripts\download-model.ps1 -Check"
    exit 1
  }
  if (-not (Test-Model $tmp)) { Write-Host "Os arquivos baixados não batem com $dir/model.lock. Nada foi copiado."; exit 1 }
  foreach ($f in $hashes.Keys) { Copy-Item (Join-Path $tmp $f) (Join-Path $dir $f) -Force }
  Write-Host "Modelo $tag salvo em $dir (SHA-256 conferido). Reinicie o backend para carregar."
} finally {
  Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
