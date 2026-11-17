#!/usr/bin/env bash
# Baixa o modelo grande (modo Servidor) da release do GitHub indicada em models/server/model.lock e confere o SHA-256.
# O repositório é privado, então o download precisa de login:
#   - GitHub CLI logado (gh auth login), ou
#   - GITHUB_TOKEN com permissão de leitura do repositório (ex.: token "fine-grained" com Contents: read).
# Uso: scripts/download-model.sh           baixa (se os arquivos da pasta não forem os esperados)
#      scripts/download-model.sh --check   só confere o que já está em models/server/
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=models/server
LOCK=$DIR/model.lock
repo=$(awk '$1=="repo"{print $2}' "$LOCK")
tag=$(awk '$1=="tag"{print $2}' "$LOCK")
files=$(awk '$1=="sha256"{print $3}' "$LOCK")
page="https://github.com/$repo/releases/tag/$tag"

sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
expected() { awk -v n="$1" '$1=="sha256" && $3==n {print $2}' "$LOCK"; }
verify() {   # verify <pasta>: 0 se os 3 arquivos existem e batem com o model.lock
  local bad=0
  for f in $files; do
    if [ ! -f "$1/$f" ]; then echo "  falta: $f"; bad=1
    elif [ "$(sha "$1/$f")" != "$(expected "$f")" ]; then echo "  SHA-256 diferente do esperado: $f"; bad=1; fi
  done
  return $bad
}

if verify "$DIR" >/dev/null; then
  echo "Modelo $tag já está em $DIR (SHA-256 conferido)."
  exit 0
fi
if [ "${1:-}" = "--check" ]; then
  echo "O modelo em $DIR não é o esperado ($tag):"; verify "$DIR" || true
  echo "Baixe com: scripts/download-model.sh"; exit 1
fi

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
echo "Baixando $tag de $repo ..."
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  args=(); for f in $files; do args+=(-p "$f"); done
  gh release download "$tag" -R "$repo" -D "$tmp" "${args[@]}"
elif [ -n "${GITHUB_TOKEN:-}" ]; then
  api="https://api.github.com/repos/$repo"
  json=$(curl -fsSL -H "Authorization: Bearer $GITHUB_TOKEN" "$api/releases/tags/$tag")
  for f in $files; do
    id=$(printf '%s' "$json" | python3 -c 'import json,sys; print(next(a["id"] for a in json.load(sys.stdin)["assets"] if a["name"]==sys.argv[1]))' "$f")
    curl -fSL --progress-bar -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/octet-stream" -o "$tmp/$f" "$api/releases/assets/$id"
  done
else
  cat >&2 <<MSG
Sem login no GitHub (o repositório é privado). Escolha uma opção:
  1) instale o GitHub CLI (https://cli.github.com), rode "gh auth login" e rode este script de novo; ou
  2) defina GITHUB_TOKEN com permissão de leitura do repositório e rode de novo; ou
  3) baixe à mão os arquivos ($(echo $files)) em $page,
     coloque em $DIR/ e confira com: scripts/download-model.sh --check
MSG
  exit 1
fi

if ! verify "$tmp"; then
  echo "Os arquivos baixados não batem com $LOCK. Nada foi copiado." >&2; exit 1
fi
for f in $files; do cp "$tmp/$f" "$DIR/$f"; done
echo "Modelo $tag salvo em $DIR (SHA-256 conferido). Reinicie o backend para carregar."
