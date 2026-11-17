# models — os modelos em uso

| Pasta | Modelo | Quem usa | No git? |
| --- | --- | --- | --- |
| `esp32/` | **soilnet 2x** `soilnet-2x-112-20261116` (TFLite int8, 112 px, 192 KB) | firmware (`firmware/esp32/src/model_data.h` é este `.tflite` convertido) e o simulador (`scripts/dev.sh`, compose `--profile sim`) | **sim** (é pequeno) |
| `server/` | **ResNet50** `resnet50-224-20261116` (ONNX, 224 px, 94 MB) | backend, modo Servidor | **não**: só o `model.lock`. Baixe com `scripts/download-model.sh` (release do GitHub, SHA-256 conferido) |

Os dois são binários: `NAOLIMPAR`/`NaoLimpar` = LIMPO ("Não precisa limpar") e `LIMPAR`/`Limpar` = SEVERO ("Precisa limpar").
Como foram treinados: [`ai-model/README.md`](../ai-model/README.md).

## esp32/
| Arquivo | Para quê |
| --- | --- |
| `model.tflite` | o modelo; `firmware/esp32/src/model_data.h` é ele em C (`ai-model/conversion/tflite_to_header.py`) |
| `labels.json` | `["NAOLIMPAR","LIMPAR"]`, ordem das saídas |
| `model_card.json` | versão, entrada, quantização, limiares (`limiar_limpar` = `DECISION_THRESHOLD`, `low_confidence_threshold` = `CONF_THRESHOLD` do `config.h`), métricas do teste |
| `metricas_modelo_final.json`, `metricas_teste.png`, `erros_teste.csv` | resultados do notebook no teste (196 fotos) |
| `particao.csv` | quais fotos foram treino e quais foram teste (reprodutibilidade) |

Os artefatos de treino (`model.keras`, `saved_model/`) ficaram com a equipe: não são usados pelo sistema.
