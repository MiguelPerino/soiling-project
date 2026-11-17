# ai-model — como os modelos são feitos

Os dois modelos do sistema saem de **notebooks do Colab**, a partir do mesmo dataset tratado. O dataset não fica no repositório.
Os modelos prontos ficam em [`../models/`](../models/README.md).

| Ordem | Notebook | Entrada | Saída | Vai para |
| --- | --- | --- | --- | --- |
| 1 | [`notebooks/1_tratamento_dataset_224.ipynb`](notebooks/1_tratamento_dataset_224.ipynb) | dataset bruto (zip, uma pasta por classe: `NaoLimpar/`, `Limpar/`) | dataset tratado (`Datasetv6_224.zip`; os notebooks 2 e 3 o leem como `Datasetv6.zip`): cada foto **enquadrada** (placa recortada) em 224×224, JPEG 95, + `preprocess.py` | os dois treinos abaixo |
| 2 | [`notebooks/2_treino_resnet_servidor.ipynb`](notebooks/2_treino_resnet_servidor.ipynb) | dataset tratado | `model.onnx`, `labels.json`, `model_card.json` (ResNet50, limiar 0,19) | release do GitHub → `models/server/` (modo Servidor) |
| 3 | [`notebooks/3_treino_soilnet_esp32.ipynb`](notebooks/3_treino_soilnet_esp32.ipynb) | dataset tratado | `model.tflite` int8, `labels.json`, `model_card.json`, `model_data.h` (soilnet 2x, 112 px, limiar 0,5) | `models/esp32/` + `firmware/esp32/` |

As saídas dos notebooks foram removidas (gráficos e logs mudam a cada execução); os números finais de cada modelo estão no
`model_card.json` dele.

## Duas classes
`NaoLimpar` = **LIMPO** ("Não precisa limpar") e `Limpar` = **SEVERO** ("Precisa limpar", a classe positiva). Os dois modelos
decidem por **limiar** em P(Limpar), não pela classe de maior probabilidade.

## O pré-processamento é parte do modelo
O sistema repete na inferência **exatamente** o caminho do treino (conferido pixel a pixel, `docs/12_MODELO_NO_SERVIDOR.md`):

| | Treino (notebooks) | Sistema |
| --- | --- | --- |
| Enquadramento | `preprocess.py` do notebook 1 | `backend/app/services/framing.py` (cópia fiel) |
| Dataset | JPEG 95, sem subamostragem | `framing.as_saved_in_dataset` |
| ResNet | 224×224 RGB 0..255, normalização dentro do ONNX | `server_model.py` |
| ESP32 | 224 → 112 bilinear → JPEG 85 → RGB565 (`device_like`) | `analysis.esp32_jpeg` (backend) + decodificação RGB565 no firmware |

Se o notebook 1 mudar, copie a célula de funções de novo para `framing.py` e **retreine os dois modelos**.

## Publicar um modelo novo
- **ResNet (servidor):** release no GitHub com os 3 arquivos → atualize `models/server/model.lock` (tag e hashes). Veja `docs/12_MODELO_NO_SERVIDOR.md`.
- **soilnet (ESP32):** copie `model.tflite`, `labels.json`, `model_card.json` e as métricas para `models/esp32/`; na raiz:
  ```bash
  .venv/bin/python ai-model/conversion/tflite_to_header.py models/esp32/model.tflite firmware/esp32/src/model_data.h
  ```
  Atualize os itens `[MODELO]` de `firmware/esp32/src/config.h` com os valores do card (versão, limiares, tamanho) e rode
  `scripts/test.sh`: `backend/tests/test_esp32_model.py` quebra se o `config.h`, o `model_data.h` e o card não baterem.
  Depois grave a placa (`docs/04_FIRMWARE_ESP32.md`).

## Retreinar com as fotos do sistema
No Histórico, corrija os rótulos e use **Exportar fotos revisadas**: o zip vem com `LIMPO/` (= `NaoLimpar`) e `SEVERO/`
(= `Limpar`). Renomeie as pastas, junte ao dataset bruto e rode os notebooks na ordem 1 → 2/3.

`conversion/tflite_to_header.py` é o único script daqui usado fora dos notebooks (gera o `model_data.h`; equivale a `xxd -i`).
