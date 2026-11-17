# 02 · Dataset e treino

## Dataset
Roboflow Universe: <https://universe.roboflow.com/amr-fph1m/solar-panel-dust-and-soiling> (≈2,3 mil imagens, classes `Clean`,
`Dusty`, `Soiled`, licença CC BY 4.0 — **cite a fonte** no trabalho). Não conseguimos confirmar o **tipo do projeto** (classificação
ou detecção). O treino precisa de **um rótulo por imagem**:
- Exporte como **classificação**: "Folder Structure" ou "Multi-label CSV". Exports de detecção (YOLO/COCO) são recusados por `prepare_data.py`.
- Baixar exige conta/chave do Roboflow (`pip install roboflow`; veja o botão "Download Dataset" do projeto). Não executamos o download.

**O sistema é binário:** `LIMPO` = "Não precisa limpar" (no modelo: `NAOLIMPAR`) e `SEVERO` = "Precisa limpar" (`LIMPAR`).
Nomes de pasta aceitos sem configuração: `LIMPO`/`SEVERO` (zip de retreino do backend), `NaoLimpar`/`Limpar` (notebook do time),
`Clean`/`Soiled` (Roboflow). **`Dusty` (poeira) não tem padrão de propósito**: olhe ~20 imagens e decida se poeira já "precisa limpar"
(`--class-map "Dusty=SEVERO"`) ou não (`--class-map "Dusty=LIMPO"`). Sem essa decisão, `prepare_data.py` para com uma mensagem.

## Suas fotos extras
Pastas por classe (ex.: `Limpar/` e `NaoLimpar/`, ou o zip "Exportar fotos revisadas" do Histórico, que vem com `LIMPO/` e `SEVERO/`),
fotografadas **do jeito que o ESP32/celular vai ver** (mesma câmera, distância e luz). Isso pesa mais que quantidade: o dataset público
tem outra câmera, outro ângulo e outro tipo de sujeira. Recomendação: separe um conjunto **só seu** para o teste final.

## Passo a passo
```bash
python -m venv .venv && .venv/bin/pip install -r ai-model/requirements.txt      # TensorFlow CPU
cd ai-model/training
python prepare_data.py --roboflow ../data/roboflow --extra ../data/minhas_fotos --class-map "Dusty=SEVERO" --out ../data/manifest.csv
#   --resplit (ignora as partições do Roboflow, sorteia 70/15/15 estratificado)
python train.py --manifest ../data/manifest.csv --size 112 --epochs 40 --out ../models/run1
cp -r ../models/run1 ../models/current
python ../conversion/tflite_to_header.py ../models/current/model.tflite ../../firmware/esp32/src/model_data.h
```
`prepare_data.py` remove duplicatas exatas (SHA‑256) entre partições — a mesma foto em treino e teste inflaria a acurácia — e imprime a contagem por partição/classe.
No fim, `train.py` **imprime os valores `[MODELO]` para colar em `firmware/esp32/src/config.h`** (tamanho, classes, índice positivo,
limiares, versão): o firmware não lê o `model_card.json` sozinho.

## O que o treino faz
Rede depthwise‑separable pequena (2 saídas, softmax), entrada 112×112 RGB, normalização `Rescaling` dentro do modelo, aumento de dados
(giros, deslocamento, brilho, contraste), pesos de classe, Adam com cosseno. As imagens passam pelo **mesmo caminho da implantação**:
esticadas para 112×112, JPEG qualidade 85 e truncadas para RGB565 (o firmware decodifica o JPEG em RGB565).
- **Melhor epoch:** maior F1 macro na validação no corte 0,5; empate ⇒ menor perda na validação (sem o desempate, com dados fáceis
  ficava o primeiro epoch a bater F1 = 1, pouco confiante).
- **Limiar de decisão** (`limiar_limpar`, `DECISION_THRESHOLD`): P(LIMPAR) ≥ limiar ⇒ "Precisa limpar". Escolhido na validação, **com o
  modelo int8**, pelo maior F1 macro (empate ⇒ o mais perto de 0,5). `--threshold` fixa um valor.
- **Trava da bomba** (`low_confidence_threshold`, `CONF_THRESHOLD`): por padrão `max(limiar, 0,5)`. Um limiar baixo classifica "Precisa
  limpar" cedo, mas a água só sai com o modelo seguro; entre os dois, o resultado vai para revisão. `--pump-threshold` muda (abaixo de 0,5 avisa).
- Ao final exporta **TFLite int8** e mede o teste **no modelo int8** (o que roda no ESP32).

Saídas em `models/<run>/`, no **mesmo formato do soilnet v1** (o simulador e o firmware já leem): `model.tflite`, `model.keras`,
`labels.json` (`["NAOLIMPAR","LIMPAR"]`), `model_card.json` (`input_size`, `positive_label`, `limiar_limpar`, `low_confidence_threshold`,
`rgb565`, `jpeg_quality`, `resize_mode`, quantização, operadores) e `metrics.json` (matriz de confusão, F1, AUC, % de limpos que
acionariam e de sujos ignorados, no limiar escolhido e no corte 0,5).

## Como ler o resultado
- Olhe a **matriz de confusão**, não só a acurácia. Os dois erros caros: "Precisa limpar" previsto como "Não precisa" (não limpa) e o contrário (gasta água à toa).
- Se a acurácia int8 cair muito frente à float, a quantização está ruim: aumente os dados de calibração.
- **Nenhum número de acurácia foi medido com fotos reais por este pipeline.** O treino rodado (17/11) usou imagens sintéticas para testar o encanamento.

## Se o modelo não couber no ESP32
`model_card.json` mostra `tflite_bytes` e a lista de operadores. A RAM real (tensor arena) só se mede no dispositivo: o firmware imprime
`arena_used_bytes()` no boot. Reduza filtros em `build_model` (`train.py`) ou a entrada (`--size 96`, alterando também `ESP32_INPUT_SIZE` no backend e `INPUT_SIZE` no firmware).
O `tiny_cnn` gera um operador a mais que o soilnet v1: `MUL` (da normalização interna). O firmware usa `AllOpsResolver`, que o inclui;
só a placa confirma.
