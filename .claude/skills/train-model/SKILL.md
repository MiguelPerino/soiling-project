---
name: train-model
description: Como os modelos binários (soilnet do ESP32 e ResNet do servidor) são treinados nos notebooks e como publicar um modelo novo no projeto. Use ao treinar, trocar de modelo, mudar o tamanho de entrada ou o enquadramento.
---
# Treino e publicação de modelos (ai-model/ e models/)

O treino é feito nos **notebooks do Colab** em `ai-model/notebooks/` (não há pipeline de treino em Python no repositório):
1. `1_tratamento_dataset_224.ipynb` — enquadra cada foto (placa recortada) em 224×224, JPEG 95. Gera o `preprocess.py`.
2. `2_treino_resnet_servidor.ipynb` — ResNet50 → `model.onnx` (servidor, limiar 0,19).
3. `3_treino_soilnet_esp32.ipynb` — soilnet 2x → `model.tflite` int8 (ESP32, 112 px, limiar 0,50) + `model_data.h`.

Classes: `NaoLimpar` → LIMPO ("Não precisa limpar"), `Limpar` → SEVERO ("Precisa limpar", positiva). Decisão por limiar, não argmax.

**Pré-processamento é parte do modelo:** `backend/app/services/framing.py` é cópia fiel do `preprocess.py` (conferida pixel a pixel).
Mudou o notebook 1? Copie as funções para `framing.py` e retreine os dois modelos. ESP32: `analysis.esp32_jpeg` reproduz o `device_like`.

Publicar soilnet novo (detalhes em `docs/02_DATASET_E_TREINO.md`):
```bash
cp <zip do notebook>/{model.tflite,labels.json,model_card.json,metricas_modelo_final.json,metricas_teste.png,erros_teste.csv,particao.csv} models/esp32/
.venv/bin/python ai-model/conversion/tflite_to_header.py models/esp32/model.tflite firmware/esp32/src/model_data.h
# atualize os itens [MODELO] de firmware/esp32/src/config.h com o card; depois:
scripts/test.sh      # test_esp32_model.py falha se config.h, model_data.h e card não baterem
```
Publicar ResNet nova: release no GitHub + `models/server/model.lock` (`docs/12_MODELO_NO_SERVIDOR.md`).
- Mude o tamanho de entrada ⇒ `ESP32_INPUT_SIZE` (backend) e `INPUT_SIZE` (firmware). Modelo do ESP32 sem o dataset tratado ⇒ `ESP32_FRAMING=none`.
- Não prometa acurácia: as métricas são as do teste dos notebooks; ninguém mediu com fotos reais pelo sistema.
