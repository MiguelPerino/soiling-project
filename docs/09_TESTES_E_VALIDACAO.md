# 09 · Testes e validação

## Rodar
`scripts/test.sh` (ou `.ps1`): backend (pytest), typecheck do front e política da bomba em C++.
Postgres: `TEST_DATABASE_URL=postgresql+psycopg://u:s@host/db_de_teste scripts/test.sh` (o banco será **apagado e recriado**; use UTF8).

## O que foi verificado (05/11/2026)
| Verificação | Resultado |
| --- | --- |
| `backend/tests` (77 testes, 17/11): API, banco, fluxo com ESP32 simulado **real via HTTP**, falhas do ESP32, modo servidor (ONNX sintético no formato do ResNet: binário, NHWC 0..255, `probs`, limiar 0,19, faixa de dúvida, enquadramento), enquadramento antes do ESP32 (byte a byte igual ao caminho do notebook), classes e tamanhos configuráveis, exportação, migração de banco antigo, assistente, simulador | passou em SQLite. PostgreSQL 16 passou antes do modo servidor e **não foi reexecutado** depois |
| `backend/tests/test_esp32_model.py` (17/11): `model_data.h` = `models/esp32/model.tflite`; `config.h` = `model_card.json` (versão, entrada, classes, índice positivo, limiares); padrões do backend; caminho completo backend → simulador com o **soilnet 2x real** (LIMPO sem bomba, SEVERO com bomba, intervalo mínimo, bloqueio sem chave) | passou. Imagens **sintéticas**: prova o encanamento, não a acurácia |
| `config.h` + `model_data.h` compilados com `g++` (17/11) | ok (só C++; o SDK do ESP32/PlatformIO não está no ambiente de teste) |
| `scripts/download-model.sh` (17/11): já baixado, pasta vazia (com `gh` simulado), arquivo corrompido, sem login, `--check` | passou. O download real da release privada (`gh`/`GITHUB_TOKEN`) e o `download-model.ps1` **não foram executados** |
| Dockerfile, etapa que confere o modelo com `model.lock` (17/11, isolada): certo, ausente, diferente, `ALLOW_NO_MODEL=1` | passou. O build completo da imagem **não** foi executado |
| Falhas do ESP32 (offline, 500, classe inventada, bomba > 60 s, não configurado) não gravam nada nem deixam arquivo órfão | testado |
| Anti path traversal no armazenamento | testado |
| `scripts/dev.sh` real (17/11): simulador com `models/esp32`, API, foto por HTTP | SEVERO aciona a bomba, LIMPO não; `/api/config` mostra soilnet 2x, ResNet50 e o enquadramento |
| Front no Chromium (Playwright) contra o stack real (PostgreSQL + API + simulador): analisar, bomba, cooldown, histórico, filtro, correção, painel, assistente, erro, mobile escuro, sem scroll horizontal, sem erros de console | passou |
| Política da bomba em C++ (incluindo virada do `millis()`) | passou |
| Docker (17/11): build das duas imagens; `docker compose --profile sim up` (PostgreSQL + app + simulador soilnet 2x): ESP32 e Servidor gravando no PostgreSQL; imagem sozinha como na Azure (sem `DATABASE_URL`/ESP32): `healthy`, front, ResNet50, ~306 MiB | passou. Corrigido no caminho: SQLite padrão da imagem em `/data` (antes não subia) |
| Terraform (17/11, 1.9.8): `init`, `validate`, `fmt -check` | passou depois de corrigir o `for_each` sobre a variável sensível do Gemini. `plan`/`apply` não executados |

| Recomendação de chuva: regra, janelas de 24 h, dados faltando, cache, plano B, rota; cartão no navegador (desktop e mobile escuro) | passou, com resposta **simulada** no formato da documentação |

## O que NÃO foi verificado (faça antes de apresentar)
1. **Acurácia real**: as métricas são as do teste dos notebooks. Meça com fotos do **seu** painel passando pelo sistema.
2. **Firmware com o soilnet 2x**: compilar no PlatformIO, gravar, checar `arena_used_bytes`, tempo de inferência, estabilidade do heap (`04_FIRMWARE_ESP32.md`, checklist).
3. **Paridade ESP32 × simulador** nas mesmas fotos.
4. **Bomba**: LED primeiro; depois MOSFET sem água; depois com água.
5. **Gemini real** (chave + `GEMINI_MODEL`): pergunta de teste com `fonte: gemini`; confira limites do plano gratuito.
6. **Open‑Meteo real**: abra `/api/weather/advice` com internet e compare com um app de previsão. **Terraform** (`plan`/`apply` numa conta Azure).
7. **Celular real**: câmera (`capture`), acesso pelo IP da rede, desempenho.
8. Auditoria de acessibilidade completa (verificado só por inspeção: textos junto com cores, alvos ≥ 44 px, rótulos, `aria-live`).

## Limitações conhecidas
- Sem migrações de banco, sem TLS, sem login de usuários, sem limitação de taxa.
- O ESP32 atende uma foto por vez; o backend espera a resposta (timeout 30 s).
- Bundle do front ~550 KB (160 KB gzip): ok em rede local.
- Fuso do painel fixo em America/Sao_Paulo.
