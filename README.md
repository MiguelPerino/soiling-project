# Soiling Detection

Protótipo que **diz, a partir de uma foto, se um painel solar precisa ou não de limpeza**. São duas classes:
**"Não precisa limpar"** (código `LIMPO`) e **"Precisa limpar"** (código `SEVERO`). Se for `SEVERO` com confiança suficiente,
o ESP32 **aciona uma pequena bomba de água** para limpar.

Há **dois modos de análise**, escolhidos no front a cada envio (não existe modo "comparar"):
- **ESP32, na hora:** o backend enquadra a foto (placa recortada, como no treino), reduz para 112×112 e manda ao ESP32 pelo Wi‑Fi;
  a rede neural roda **no ESP32**, que também decide a bomba.
- **Servidor:** um modelo grande opcional (ONNX; hoje ResNet50 `resnet50-224-20261116`, 2 classes, limiar 0,19) roda no backend. **Nunca aciona a bomba.**

```
Celular/PC (React) ──foto──▶ Backend (FastAPI) ──JPEG 112×112──▶ ESP32 (TFLite int8, 2 classes) ──▶ bomba
      ▲                        │  ONNX Runtime (modo servidor, 2 classes, sem bomba)
      └──── resultado ─────────┴──── grava arquivo + linha no banco (PostgreSQL; SQLite em dev)
                                         ▲
                      Gemini (opcional): resumos e busca em português
```

**Modelos atuais** (os dois treinados com o mesmo dataset tratado: fotos enquadradas em 224×224; `models/README.md`):

| Modo | Modelo | Entrada | Limiar P(Limpar) | Teste do time | Onde está |
| --- | --- | --- | --- | --- | --- |
| ESP32 | `soilnet-2x-112-20261116` (TFLite int8, 192 KB) | 112×112 | 0,50 (decisão e bomba) | 88,3% (196 fotos) | `models/esp32/` e `firmware/esp32/src/model_data.h` (no git) |
| Servidor | `resnet50-224-20261116` (ONNX, 94 MB) | 224×224 | 0,19 | 95,3% (191 fotos) | release do GitHub → `models/server/` (`scripts/download-model.sh`) |

Como foram treinados: `ai-model/README.md` (notebooks em `ai-model/notebooks/`). O dataset **não** entra no repositório.

| Pasta | O que tem |
| --- | --- |
| `frontend/` | React + TypeScript + Tailwind + Recharts: analisar, histórico, painel, assistente |
| `backend/` | FastAPI, PostgreSQL (SQLite nos testes), cliente do ESP32, modelo grande opcional (ONNX), assistente Gemini |
| `firmware/esp32/` | PlatformIO: servidor HTTP, decodificação JPEG, TFLite Micro, bomba com política de segurança |
| `ai-model/` | Notebooks: tratamento do dataset (enquadramento 224), treino da ResNet (servidor) e do soilnet (ESP32); conversor `.tflite` → `model_data.h` |
| `models/` | Os modelos em uso: `esp32/` (soilnet 2x, versionado) e `server/` (ResNet50, baixado da release) |
| `backend/app/services/weather.py` | Recomendação de chuva (Open‑Meteo): só informa, nunca aciona a bomba |
| `tools/esp32_simulator/` | **ESP32 de mentira** com o mesmo protocolo: permite testar e ensaiar sem hardware |
| `infra/terraform/` | Implantação na Azure (Terraform): site público só com o modelo grande; o ESP32 fica local |
| `docs/` | Documentação (comece por `docs/00_VISAO_GERAL.md`) |
| `.claude/skills/` | Skills para Claude Code e Codex (`AGENTS.md` é o contexto principal) |
| `historico/` | Registro do que foi feito antes da mudança de rumo (só documentação) |

## Rodar

```bash
scripts/setup.sh                    # uma vez. Windows: scripts\setup.ps1 (cria .venv, instala, compila o front)
scripts/dev.sh                      # ESP32 SIMULADO + API (SQLite) -> http://localhost:8000
scripts/dev-esp32.sh 10.168.71.63   # ESP32 REAL: passe o IP que o monitor serial imprime. Windows: scripts\dev-esp32.ps1
```
Ou com Docker (PostgreSQL incluso): `cp .env.example .env`, edite, `docker compose --profile sim up -d --build`.

- O `dev.sh` roda o simulador com **o mesmo modelo da placa** (`models/esp32`, soilnet 2x).
- **Gravar o firmware:** passo a passo (Wi‑Fi em `secrets.h`, `pio run -t upload`, monitor serial, teste do LED) em `docs/04_FIRMWARE_ESP32.md`, seção "Primeiro teste na placa".
  O pino da bomba está em `GPIO 2` (LED azul da placa) para validar sem bomba ligada.
- **Modelo grande (servidor):** `scripts/download-model.sh` (Windows: `scripts\download-model.ps1`; o `setup` já chama) baixa os 3 arquivos da
  [release `modelo-resnet50-20261116`](https://github.com/libinayantonini-sketch/soiling-project/releases/tag/modelo-resnet50-20261116) para `models/server/`
  e confere o SHA-256 com `models/server/model.lock`. O repositório é privado: precisa de `gh auth login` (GitHub CLI) ou `GITHUB_TOKEN`.
  Os pesos não ficam no git (94 MB). Veja `docs/12_MODELO_NO_SERVIDOR.md`.
  Sem o modelo, só o modo servidor fica indisponível; o modo ESP32 segue normal (`/api/config` mostra o motivo).
- Fotos enviadas e corrigidas à mão saem em zip pela tela de histórico (`LIMPO/` e `SEVERO/`) para retreinar nos notebooks (`docs/02_DATASET_E_TREINO.md`).

## O que está validado e o que não está (leia antes da apresentação)

| Parte | Estado |
| --- | --- |
| Backend, banco (SQLite **e** PostgreSQL 16), protocolo com ESP32 simulado | testado automaticamente: 76 testes em SQLite. PostgreSQL 16 passou antes do modo servidor (10/11) e **não foi reexecutado** depois |
| **Firmware no ESP32 (12/11, soilnet v1)** | **compilado, gravado e rodando numa placa esp32dev** com o modelo anterior (soilnet v1): carrega, conecta no Wi‑Fi, responde ao backend, e uma imagem `SEVERO` acendeu o LED azul (GPIO 2). Houve folga de memória (relato da equipe) |
| **Firmware com o soilnet 2x (17/11)** | `config.h` e `model_data.h` atualizados e coerentes com o card (teste automático); compilam em `g++`. **Não compilado no PlatformIO nem gravado na placa**: mesmos operadores do v1, ativações estimadas iguais (~67 KB), flash 192 KB |
| Enquadramento antes do ESP32 | o JPEG enviado é byte a byte o do caminho do notebook (tratamento → 224 JPEG 95 → 112 → JPEG 85); caminho completo com o soilnet 2x real no simulador testado |
| Modo servidor (modelo grande ONNX) | testado com um ONNX **sintético** no formato do ResNet (binário, limiar, faixa de dúvida, modelo ausente/inválido, exportação). Enquadramento idêntico ao do notebook (conferido pixel a pixel). A ResNet50 real carrega e roda (≈35–55 ms/foto na CPU), só com imagens sintéticas. Acurácia em fotos reais: **não medida** |
| Front no navegador (fluxo completo, mobile, tema escuro) | testado com Playwright contra o stack real, usando o simulador |
| Política de segurança da bomba (C++) | testada no computador |
| **Acurácia com fotos reais na placa** | **não medida por nós**: só as métricas de teste dos notebooks. Limiares alinhados: ESP32 0,50 na placa e no backend (`LOW_CONFIDENCE_THRESHOLD`) |
| **Bomba real, uso contínuo, tempo de inferência medido, Wi‑Fi da universidade** | **não testados**: só o LED foi verificado, com imagens de cor lisa (prova o caminho, não a acurácia) |
| Gemini real | **não testado** contra a API (sem rede no ambiente de construção); testado com cliente falso |
| Docker, Terraform | build completo da imagem e Terraform **não executados**; só a etapa do Dockerfile que confere o modelo grande rodou (17/11) e o Terraform teve a sintaxe verificada |

Detalhes e checklist: `docs/09_TESTES_E_VALIDACAO.md`. Perguntas em aberto: `docs/11_PENDENCIAS.md`.