# Soiling Detection

Protótipo que **diz, a partir de uma foto, se um painel solar precisa ou não de limpeza**. São duas classes:
**"Não precisa limpar"** (código `LIMPO`) e **"Precisa limpar"** (código `SEVERO`). Se for `SEVERO` com confiança suficiente,
o ESP32 **aciona uma pequena bomba de água** para limpar.

Há **dois modos de análise**, escolhidos no front a cada envio (não existe modo "comparar"):
- **ESP32, na hora:** o backend redimensiona a foto e manda ao ESP32 pelo Wi‑Fi; a rede neural roda **no ESP32**, que também decide a bomba.
- **Servidor:** um modelo grande opcional (ONNX; hoje ResNet50 `resnet50-224-20261116`, 2 classes, limiar 0,19) roda no backend. **Nunca aciona a bomba.**

```
Celular/PC (React) ──foto──▶ Backend (FastAPI) ──JPEG 112×112──▶ ESP32 (TFLite int8, 2 classes) ──▶ bomba
      ▲                        │  ONNX Runtime (modo servidor, 2 classes, sem bomba)
      └──── resultado ─────────┴──── grava arquivo + linha no banco (PostgreSQL; SQLite em dev)
                                         ▲
                      Gemini (opcional): resumos e busca em português
```

**Modelo atual do ESP32:** `soilnet-112-20261110` (v1, da equipe de IA): binário NAOLIMPAR/LIMPAR, entrada 112×112, int8, 114 KB.
Mapeado para `LIMPO`/`SEVERO`; decide `SEVERO` quando P(LIMPAR) ≥ 0,41. Detalhes em `docs/04_FIRMWARE_ESP32.md`.
Tamanho de entrada e classes são configuráveis (`ESP32_INPUT_SIZE`, `ESP32_CLASSES`, `SERVER_INPUT_SIZE`, `.env.example`).
O dataset **não** entra no repositório: só o modelo treinado e as imagens novas que voltam do sistema (export em zip).

| Pasta | O que tem |
| --- | --- |
| `frontend/` | React + TypeScript + Tailwind + Recharts: analisar, histórico, painel, assistente |
| `backend/` | FastAPI, PostgreSQL (SQLite nos testes), cliente do ESP32, modelo grande opcional (ONNX), assistente Gemini |
| `firmware/esp32/` | PlatformIO: servidor HTTP, decodificação JPEG, TFLite Micro, bomba com política de segurança |
| `ai-model/` | Preparo do dataset Roboflow, treino Keras, exportação TFLite int8 |
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

- O `dev.sh` usa o **modelo real soilnet** no simulador quando `ai-model/models/current/` existe; sem ele, cai num modelo sintético de demonstração.
- **Gravar o firmware:** passo a passo (Wi‑Fi em `secrets.h`, `pio run -t upload`, monitor serial, teste do LED) em `docs/04_FIRMWARE_ESP32.md`, seção "Primeiro teste na placa".
  O pino da bomba está em `GPIO 2` (LED azul da placa) para validar sem bomba ligada.
- **Modelo grande (servidor):** coloque `model.onnx`, `labels.json` e `model_card.json` (os 3 que o notebook gera) em `models/server/`, na raiz, e reinicie.
  Os pesos não ficam no git (94 MB). Veja `docs/12_MODELO_NO_SERVIDOR.md`.
  Sem o modelo, só o modo servidor fica indisponível; o modo ESP32 segue normal (`/api/config` mostra o motivo).
- Fotos enviadas e corrigidas à mão saem em zip pela tela de histórico, no formato que `prepare_data.py --extra` lê para retreinar.

## O que está validado e o que não está (leia antes da apresentação)

| Parte | Estado |
| --- | --- |
| Backend, banco (SQLite **e** PostgreSQL 16), protocolo com ESP32 simulado | testado automaticamente: 58 testes em SQLite. PostgreSQL 16 passou antes do modo servidor (10/11) e **não foi reexecutado** depois |
| **Firmware no ESP32 (12/11)** | **compilado, gravado e rodando numa placa esp32dev**: o modelo soilnet carrega, conecta no Wi‑Fi, responde ao backend, e uma imagem classificada `SEVERO` acendeu o LED azul (GPIO 2) com a regra de bomba. Houve folga de memória (relato da equipe) |
| Modo servidor (modelo grande ONNX) | testado com um ONNX **sintético** no formato do ResNet (binário, limiar, faixa de dúvida, modelo ausente/inválido, exportação). A ResNet50 real carrega e roda (≈20 ms/foto na CPU), só com imagens sintéticas. Acurácia em fotos reais e o enquadramento do notebook: **pendentes** |
| Front no navegador (fluxo completo, mobo mesmo contêiner serve a API e o front compilado (sem CORS e com um deploy só). Detalhes e comandos: `infra/terraform/README.md`.o mesmo contêiner serve a API e o front compilado (sem CORS e com um deploy só). Detalhes e comandos: `infra/terraform/README.md`.ile, tema escuro) | testado com Playwright contra o stack real, usando o simulador |
| Pipeline de treino → TFLite int8 → simulador | testado de ponta a ponta com imagens **sintéticas** (prova o encanamento, não a acurácia) |
| Política de segurança da bomba (C++) | testada no computador |
| **Acurácia com fotos reais na placa** | **não medida por nós**: só as métricas de treino da equipe. Limiar 0,41 (ESP32) vs. 0,60 (backend marca baixa confiança) ainda a alinhar |
| **Bomba real, uso contínuo, tempo de inferência medido, Wi‑Fi da universidade** | **não testados**: só o LED foi verificado, com imagens de cor lisa (prova o caminho, não a acurácia) |
| Gemini real | **não testado** contra a API (sem rede no ambiente de construção); testado com cliente falso |
| Docker, Terraform | **não executados** (sem Docker/Terraform aqui); Terraform só teve a sintaxe verificada |

Detalhes e checklist: `docs/09_TESTES_E_VALIDACAO.md`. Perguntas em aberto: `docs/11_PENDENCIAS.md`.