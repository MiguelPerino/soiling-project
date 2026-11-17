# 02 · Dataset e treino

Os dois modelos são **binários** e saem de notebooks do Colab que estão em `ai-model/notebooks/` (resumo em `ai-model/README.md`):

| Pasta do dataset | Código no sistema | Na tela | Papel |
| --- | --- | --- | --- |
| `NaoLimpar/` | `LIMPO` | Não precisa limpar | classe negativa (índice 0) |
| `Limpar/` | `SEVERO` | Precisa limpar | classe positiva (índice 1): a única que pode acionar a bomba |

## Dataset
O dataset **não fica no repositório**. A equipe mantém duas versões (nomes como estão nos notebooks):
- **bruto** (`Datasetv5.zip` no notebook 1): as fotos como foram reunidas, uma subpasta por classe. Inclui fotos derivadas do Roboflow
  "solar-panel-dust-and-soiling" (CC BY 4.0 — **cite a fonte** no trabalho), fotos da equipe e algumas sintéticas (`synth__`).
- **tratado** (`Datasetv6_224.zip`, saída do notebook 1; os notebooks 2 e 3 o leem com o nome `Datasetv6.zip`): o mesmo dataset
  enquadrado em 224×224. É dele que os dois treinos partem.

Fotos novas vêm do próprio sistema: no Histórico, corrija o rótulo ("Não precisa limpar" / "Precisa limpar") e use
**Exportar fotos revisadas** (`GET /api/export/training.zip`): o zip vem com `LIMPO/` e `SEVERO/` — renomeie para `NaoLimpar/` e
`Limpar/` e junte ao dataset bruto.

## 1. Tratamento: `1_tratamento_dataset_224.ipynb`
Para cada foto: corrige a orientação, remove bordas uniformes, **acha a placa pela cor e recorta um quadrado em volta dela**
(sem placa: recorte central), completa fotos muito largas com fundo desfocado da própria foto e salva **224×224 em JPEG 95**
(sem subamostragem de cor). Nenhuma mudança de cor. Também remove duplicatas exatas e gera o `preprocess.py` com esse código.

**O sistema aplica exatamente esse código na inferência** (`backend/app/services/framing.py`, conferido pixel a pixel contra o
notebook), antes dos dois modelos. Mudou o notebook? Copie as funções de novo para `framing.py` e retreine os dois modelos.

## 2. ResNet do servidor: `2_treino_resnet_servidor.ipynb`
ResNet50 pré-treinada no ImageNet (PyTorch), 224×224, aumento com rotações de 90°, ângulo aleatório e espelhamento; teste separado por
grupo de foto original (cópias e sintéticas ficam juntas), validação cruzada para escolher o limiar e treino final com todo o treino.
Exporta `model.onnx` (entrada NHWC 0..255, normalização e softmax embutidos), `labels.json`, `model_card.json`.
**Modelo atual:** `resnet50-224-20261116`, limiar 0,19. Publicação: release do GitHub + `models/server/model.lock` (`docs/12_MODELO_NO_SERVIDOR.md`).

## 3. soilnet do ESP32: `3_treino_soilnet_esp32.ipynb`
CNN própria pequena (`soilnet`, preset `2x`: depthwise-separable com atalhos residuais), do zero, 112×112.
As imagens passam pelo **mesmo caminho que a foto faz até o ESP32** (`device_like`): 224 tratada → 112 bilinear → JPEG 85 → RGB565.
Antes de treinar, o notebook confere se a rede **cabe no ESP32** (flash ≤ 300 KB, arena ≤ 96 KB). Teste separado por grupo de foto,
conferência de vazamento, validação cruzada para calibrar os limiares e treino final com todo o treino. Mede o teste em float **e em int8**
(o que roda na placa). Exporta `model.tflite` int8, `labels.json` (`["NAOLIMPAR","LIMPAR"]`), `model_card.json` e `model_data.h`.

**Modelo atual:** `soilnet-2x-112-20261116` (135 mil parâmetros, 192 KB), limiar 0,50. Teste do time (196 fotos, int8): acurácia 88,3%
(IC95 83,7–92,3%), F1 macro 0,88, AUC 0,91; 6,9% das limpas acionariam a bomba e 17,0% das sujas seriam ignoradas.

### Publicar um modelo novo do ESP32
1. Copie do zip do notebook para `models/esp32/`: `model.tflite`, `labels.json`, `model_card.json`, `metricas_modelo_final.json`,
   `metricas_teste.png`, `erros_teste.csv`, `particao.csv`.
2. Na raiz: `.venv/bin/python ai-model/conversion/tflite_to_header.py models/esp32/model.tflite firmware/esp32/src/model_data.h`.
3. Atualize os itens `[MODELO]` de `firmware/esp32/src/config.h` com o card: `MODEL_VERSION` = `version`, `INPUT_SIZE` = `input_size`,
   `DECISION_THRESHOLD` = `limiar_limpar`, `CONF_THRESHOLD` = `low_confidence_threshold` (e `POSITIVE_CLASS` = posição de `positive_label`).
   Se o tamanho de entrada mudar: `ESP32_INPUT_SIZE` no backend. Se o modelo não foi treinado com o dataset tratado: `ESP32_FRAMING=none`.
4. `scripts/test.sh`: `backend/tests/test_esp32_model.py` falha se `config.h`, `model_data.h` e card não baterem, e roda o caminho
   completo backend → simulador com o modelo novo. As duas imagens de `backend/tests/fixtures/esp32/` são escolhidas pelo que o modelo
   responde: se o modelo novo responder diferente, gere outras (veja o `LEIA.md` da pasta).
5. Grave a placa (`docs/04_FIRMWARE_ESP32.md`). O simulador (`scripts/dev.sh`) já usa `models/esp32` automaticamente.

## Como ler o resultado
- Olhe a **matriz de confusão** do teste int8, não só a acurácia. Os dois erros caros: "Precisa limpar" previsto como "Não precisa"
  (painel sujo fica sujo) e o contrário (gasta água à toa).
- As métricas são as do notebook do time, num teste de 196 fotos. **Ninguém mediu ainda com fotos novas do painel real pelo sistema.**

## Se o modelo não couber no ESP32
O notebook 3 avisa antes de treinar ("Cabe no ESP32?"). A RAM real só se mede na placa: o firmware imprime `arena_used_bytes()` no boot.
Use `SOIL_PRESET="1x"` ou reduza `IMG_SIZE` (e mude `ESP32_INPUT_SIZE` no backend e `INPUT_SIZE` no firmware).
