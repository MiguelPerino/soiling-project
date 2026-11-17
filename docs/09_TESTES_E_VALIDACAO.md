# 09 · Testes e validação

## Rodar
`scripts/test.sh` (ou `.ps1`): backend (pytest), pipeline de dados do `ai-model`, typecheck do front e política da bomba em C++.
Postgres: `TEST_DATABASE_URL=postgresql+psycopg://u:s@host/db_de_teste scripts/test.sh` (o banco será **apagado e recriado**; use UTF8).

## O que foi verificado (05/11/2026)
| Verificação | Resultado |
| --- | --- |
| `backend/tests` (71 testes): API, banco, fluxo com ESP32 simulado **real via HTTP**, falhas do ESP32, modo servidor (ONNX sintético no formato do ResNet: binário, NHWC 0..255, `probs`, limiar 0,19, faixa de dúvida, enquadramento do notebook), o modelo real soilnet v1 no simulador e no backend, classes e tamanhos configuráveis, exportação, migração de banco antigo, assistente, simulador | passou em SQLite. PostgreSQL 16 passou antes do modo servidor e **não foi reexecutado** depois |
| `scripts/download-model.sh` (17/11): já baixado, pasta vazia (com `gh` simulado), arquivo corrompido, sem login, `--check` | passou. O download real da release privada (`gh`/`GITHUB_TOKEN`) e o `download-model.ps1` **não foram executados** |
| Dockerfile, etapa que confere o modelo com `model.lock` (17/11, isolada): certo, ausente, diferente, `ALLOW_NO_MODEL=1` | passou. O build completo da imagem **não** foi executado |
| Falhas do ESP32 (offline, 500, classe inventada, bomba > 60 s, não configurado) não gravam nada nem deixam arquivo órfão | testado |
| Anti path traversal no armazenamento | testado |
| `ai-model/tests` (10 testes): classes binárias iguais ao `config.h`, mapa de pastas (Dusty exige decisão), formatos Roboflow (pasta e CSV), duplicatas, partição estratificada, métricas por limiar, escolha do limiar, RGB565 igual ao simulador, card no formato do soilnet, recusa de detecção | passou |
| Treino Keras → TFLite int8 → simulador → backend (17/11, TensorFlow 2.21, dataset **sintético** `Limpar`/`NaoLimpar`) | funcionou: 28 KB, entrada/saída int8 iguais às do soilnet v1, sujas → SEVERO com bomba, limpas → LIMPO. Acurácia 100% num dataset trivial **não significa nada** para fotos reais. Virou teste fixo: `backend/tests/test_trained_esp32_model.py` |
| Front no Chromium (Playwright) contra o stack real (PostgreSQL + API + simulador): analisar, bomba, cooldown, histórico, filtro, correção, painel, assistente, erro, mobile escuro, sem scroll horizontal, sem erros de console | passou |
| Política da bomba em C++ (incluindo virada do `millis()`) | passou |
| Sintaxe do Terraform (python-hcl2) | ok |

| Recomendação de chuva: regra, janelas de 24 h, dados faltando, cache, plano B, rota; cartão no navegador (desktop e mobile escuro) | passou, com resposta **simulada** no formato da documentação |

## O que NÃO foi verificado (faça antes de apresentar)
1. **Acurácia real**: treinar com o dataset + suas fotos e ler `metrics.json`. Meça com fotos do **seu** painel.
2. **Firmware**: compilar, gravar, checar `arena_used_bytes`, tempo de inferência, estabilidade do heap (`04_FIRMWARE_ESP32.md`, checklist).
3. **Paridade ESP32 × simulador** nas mesmas fotos.
4. **Bomba**: LED primeiro; depois MOSFET sem água; depois com água.
5. **Gemini real** (chave + `GEMINI_MODEL`): pergunta de teste com `fonte: gemini`; confira limites do plano gratuito.
6. **Open‑Meteo real**: abra `/api/weather/advice` com internet e compare com um app de previsão. **Docker** (`docker compose up --build`) e **Terraform** (`plan`/`apply`).
7. **Celular real**: câmera (`capture`), acesso pelo IP da rede, desempenho.
8. Auditoria de acessibilidade completa (verificado só por inspeção: textos junto com cores, alvos ≥ 44 px, rótulos, `aria-live`).

## Limitações conhecidas
- Sem migrações de banco, sem TLS, sem login de usuários, sem limitação de taxa.
- O ESP32 atende uma foto por vez; o backend espera a resposta (timeout 30 s).
- Bundle do front ~550 KB (160 KB gzip): ok em rede local.
- Fuso do painel fixo em America/Sao_Paulo.
