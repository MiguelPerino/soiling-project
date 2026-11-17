---
name: train-model
description: Preparar o dataset (Roboflow + fotos extras), treinar o classificador binário Keras e exportar TFLite int8 para o ESP32. Use ao treinar, avaliar, trocar a rede ou mudar o tamanho de entrada.
---
# Treino (ai-model/) — modelo BINÁRIO do ESP32

```bash
.venv/bin/pip install -r ai-model/requirements.txt
cd ai-model/training
python prepare_data.py --roboflow ../data/roboflow --extra ../data/minhas_fotos --class-map "Dusty=SEVERO" --out ../data/manifest.csv   # --resplit
python train.py --manifest ../data/manifest.csv --size 112 --epochs 40 --out ../models/run1
cp -r ../models/run1 ../models/current
python ../conversion/tflite_to_header.py ../models/current/model.tflite ../../firmware/esp32/src/model_data.h
```
- Duas classes: `LIMPO` (NAOLIMPAR, índice 0) e `SEVERO` (LIMPAR, índice 1, positiva). Pastas aceitas: LIMPO/SEVERO, NaoLimpar/Limpar, Clean/Soiled. `Dusty` exige `--class-map`.
- A saída segue o formato do soilnet v1 (labels NAOLIMPAR/LIMPAR, `positive_label`, `limiar_limpar`, `low_confidence_threshold`, `rgb565`).
  `train.py` imprime o trecho `[MODELO]` do `firmware/esp32/src/config.h`: cole-o, regenere o `model_data.h` e confira `ESP32_INPUT_SIZE` no backend.
- Decisão por limiar (escolhido na validação int8), não argmax. A bomba exige `max(limiar, 0,5)` por padrão.
- Treino imita a implantação: esticada, JPEG 85, RGB565. Mude `--size` ⇒ mude `ESP32_INPUT_SIZE` (backend) e `INPUT_SIZE` (firmware).
- Meça sempre o **int8** (`teste_tflite_int8` em `metrics.json`). Olhe a matriz de confusão.
- BatchNorm com `momentum=0.9` de propósito. Melhor epoch: F1 no corte 0,5, desempate pela menor perda de validação.
- `backend/tests/test_trained_esp32_model.py` prova que a saída do treino roda no simulador e no backend (modelo sintético em fixtures).
- Não prometa acurácia sem ter treinado com dados reais.
