# 12 · Modelo grande no servidor (ONNX, binário)

Além do modelo pequeno do ESP32, o backend pode rodar um **modelo grande** (hoje uma ResNet50) para uma análise mais robusta.
São **dois modos**, escolhidos no front para cada foto. Não existe modo "comparar". Os dois são **binários**:
`LIMPO` = "Não precisa limpar" e `SEVERO` = "Precisa limpar".

| | `esp32` | `server` |
| --- | --- | --- |
| Onde roda | no ESP32 (Wi‑Fi local) | no backend, ONNX Runtime na CPU |
| Aciona a bomba | sim, pela política do firmware | **nunca** |
| Classes | `ESP32_CLASSES` = `LIMPO,SEVERO` (soilnet v1: NAOLIMPAR/LIMPAR) | `labels.json` com 2 nomes + `classe_positiva` do card (NaoLimpar/Limpar) |
| Decisão | P(LIMPAR) ≥ 0,41 (firmware) | P(Limpar) ≥ `decisao.limiar` do card (hoje **0,19**) |
| "Revisar" | confiança < `LOW_CONFIDENCE_THRESHOLD` | faixa de dúvida: limiar ≤ P(Limpar) < `SERVER_REVIEW_UNTIL` (0,50) |
| Tamanho de entrada | `ESP32_INPUT_SIZE` (112) | `SERVER_INPUT_SIZE`, ou `preprocessamento.img_size` do card (224) |

O dataset **não** faz parte do repositório, e os pesos também não (`models/server/` está no `.gitignore`: o ONNX tem 94 MB).
As fotos novas voltam pelo sistema (exportação abaixo).

## Onde o modelo fica e como chega à pasta
- **Fonte oficial:** a release do GitHub [`modelo-resnet50-20261116`](https://github.com/libinayantonini-sketch/soiling-project/releases/tag/modelo-resnet50-20261116),
  com `model.onnx`, `labels.json` e `model_card.json`.
- **No git:** só `models/server/model.lock` (release, versão e o SHA-256 de cada arquivo). É ele que diz qual modelo o código espera.
- **Baixar:** `scripts/download-model.sh` (Windows: `scripts\download-model.ps1`), chamado também pelo `setup`. Baixa da release para
  `models/server/` e confere o SHA-256; se algo não bater, não copia nada. `--check` (`-Check`) só confere a pasta.
  O repositório é privado: o script usa o GitHub CLI logado (`gh auth login`) ou `GITHUB_TOKEN` (leitura do repositório);
  sem nenhum dos dois, explica como baixar à mão pela página da release.
- **Docker/Azure:** o `docker build` confere a pasta com o `model.lock` e **falha** se o modelo faltar ou for outro
  (na Azure o modo Servidor é o único que funciona). Para construir sem modelo de propósito: `--build-arg ALLOW_NO_MODEL=1`.
- **Trocar de modelo:** nova release com os 3 arquivos → atualize `tag`, `versao` e os hashes no `model.lock`
  (`sha256sum model.onnx labels.json model_card.json`) → commit → `scripts/download-model.sh` em cada máquina.

## Modelo atual
`resnet50-224-20261116` (notebook `treino_placas_resnet_tratado.ipynb` do time). O card informa, sobre 191 fotos de teste do notebook:
acurácia 95,3% no limiar 0,19 (95,8% no corte 0,5), AUC 0,99, 7 limpas classificadas "Precisa limpar" e 2 sujas classificadas
"Não precisa limpar". **Esses números são do notebook; este sistema não os mediu** (não temos as fotos de teste aqui).

## O que a equipe entrega: os 3 arquivos que o notebook gera
Eles vão para `models/server/` na raiz do repositório (ou aponte `SERVER_MODEL_DIR`) pelo `scripts/download-model.sh`. Em Docker essa pasta vai para `/models/server`.

| Arquivo | Conteúdo |
| --- | --- |
| `model.onnx` | **2 saídas**. Entrada NHWC `(N,H,W,3)` ou NCHW `(N,3,H,W)`, float32 RGB. O layout é lido do próprio ONNX (ou de `onnx.input.layout`) |
| `labels.json` | os 2 nomes na ordem das saídas: `["NaoLimpar","Limpar"]` (ou já `["LIMPO","SEVERO"]`) |
| `model_card.json` | o card do notebook. Campos lidos abaixo |

Campos do `model_card.json` que o backend usa (`backend/app/services/server_model.py`):

| Campo | Para quê | Se faltar |
| --- | --- | --- |
| `versao` (ou `version`) | aparece em cada análise | "desconhecida" |
| `classe_positiva` | qual nome do `labels.json` significa "Precisa limpar" (vira `SEVERO`; o outro vira `LIMPO`) | obrigatório, salvo se `labels.json` já for `LIMPO`/`SEVERO` |
| `decisao.limiar` | P(positiva) ≥ limiar ⇒ "Precisa limpar" | 0,5 |
| `decisao.revisao_ate` (opcional) | topo da faixa de dúvida; manda sobre `SERVER_REVIEW_UNTIL` | `SERVER_REVIEW_UNTIL` |
| `onnx.input.faixa` | `[0,255]` ⇒ pixels crus, a normalização vive dentro do ONNX | 0..1 normalizado com `mean`/`std` (ImageNet) |
| `onnx.output.name` = `probs` (ou `output: "probs"`) | a saída já é probabilidade; **não** aplica softmax de novo | aplica softmax (logits) |
| `preprocessamento.img_size` | lado da entrada | `input_size`, depois o tamanho fixo do ONNX, depois 224 |
| `preprocessamento.enquadramento` (opcional) | `panel`, `center` ou `none` (abaixo) | `SERVER_FRAMING` (padrão `panel`) |
| `preprocessamento.margem` / `frac_central` / `wide_ratio` (opcionais) | parâmetros do enquadramento | 0,06 / 0,90 / 1,5 (os do notebook) |

Regras (iguais às do ESP32 binário):
- **Decisão por limiar, não por maior probabilidade.** Com limiar 0,19, P(Limpar) = 0,30 já é "Precisa limpar".
- `confidence` = probabilidade da classe escolhida (não é percentual de sujeira).
- **Faixa de dúvida**: limiar ≤ P(Limpar) < `SERVER_REVIEW_UNTIL` ⇒ "Precisa limpar" com `low_confidence=true` e ação "revisar".
  O valor 0,50 é **provisório**: escolha-o medindo P(Limpar) foto a foto no conjunto de teste.
- `/api/config` expõe `engines.server.limiar` e `revisao_ate`; o front marca o limiar na barra de probabilidade.
- O backend recusa o modelo (modo servidor indisponível, com o motivo) se o ONNX não tiver 2 saídas, se faltar `classe_positiva`
  ou se o limiar estiver fora de (0, 1). O modo ESP32 segue normal.
- Trocar de modelo = trocar os 3 arquivos e reiniciar o backend. Nenhum código muda.

### Enquadramento (o mesmo do treino)
O ResNet foi treinado com fotos tratadas pelo notebook `tratamento_dataset_224.ipynb`, e a inferência usa **o mesmo código**
(`backend/app/services/framing.py`, cópia do `preprocess.py` que o notebook gera; depende de `opencv-python-headless`):
1. remove faixas uniformes nas bordas (barras pretas/brancas);
2. acha a placa pela cor (azul ou cinza/preta) e recorta um quadrado em volta dela, com 6% de folga;
   se não achar (ou a placa ocupar menos de 12% da foto), recorte quadrado central de 90% do lado menor;
3. região alongada demais (> 1,5): completa o quadrado com um fundo desfocado da própria foto, em vez de cortar a placa;
4. redimensiona para 224×224. Nenhuma mudança de cor.

Conferido em 17/11: rodando o código do notebook e o do backend lado a lado em 9 imagens (os 4 caminhos acima, tarja preta,
placa ocupando tudo, foto pequena), a saída foi **idêntica pixel a pixel**. Se o notebook mudar, copie a célula de novo e retreine.
Diferenças que sobram: o front reduz a foto para no máximo `UPLOAD_MAX_SIDE` (512 px) antes de enviar, e no treino as fotos tratadas
foram regravadas em JPEG 95; são pequenas, mas não foram medidas.
`SERVER_FRAMING=none` volta a esticar a foto inteira (só para modelos treinados sem enquadramento).

## Variáveis (ver `.env.example`)
| Variável | Padrão | Para quê |
| --- | --- | --- |
| `ESP32_INPUT_SIZE` | 112 | lado da foto enviada ao ESP32 (igual ao treino/firmware). `INPUT_SIZE` ainda é aceito |
| `ESP32_CLASSES` | `LIMPO,SEVERO` | classes do modelo do ESP32 (só estas duas são aceitas). Se o ESP32 devolver outra, a API responde 502 e não grava |
| `SERVER_MODEL_DIR` | `models/server` | pasta do modelo grande |
| `SERVER_INPUT_SIZE` | 0 | lado da entrada do modelo grande; 0 = usar o card |
| `SERVER_REVIEW_UNTIL` | 0.5 | topo da faixa de dúvida (provisório) |
| `SERVER_FRAMING` | `panel` | enquadramento antes do modelo grande: `panel`, `center` ou `none`; o card manda se tiver `preprocessamento.enquadramento` |
| `UPLOAD_MAX_SIDE` | 512 | maior lado da foto que o front envia e que fica guardada |

O front envia uma foto de até `UPLOAD_MAX_SIDE` px. O backend guarda essa foto e gera, a partir dela, a versão de cada modelo
(estica para quadrado). Por isso os tamanhos de entrada podem mudar sem mexer no front.

## Retreino com as fotos novas
No Histórico, corrija o rótulo das fotos ("Não precisa limpar" / "Precisa limpar"; precisa da chave de administrador, se
configurada) e use **Exportar fotos revisadas** (`GET /api/export/training.zip`). O zip tem as pastas `LIMPO/` (= NaoLimpar) e
`SEVERO/` (= Limpar) e um `labels.csv`. As fotos saem no tamanho guardado; cada treino as redimensiona.

## Fora do escopo desta mudança
`ai-model/training/` (pipeline Keras → TFLite do ESP32) ainda assume 3 classes e não foi alterado: o modelo do ESP32 vem do
notebook do time. O firmware, o protocolo e `tflite_engine.py` (simulador com o soilnet real) também não mudaram.

## O que foi e o que não foi testado
Testado automaticamente (`backend/tests/test_server_engine.py`), com um ONNX **sintético no mesmo formato do ResNet** (NHWC 0..255,
saída `probs`, NaoLimpar/Limpar, limiar 0,19): carga, limiar, faixa de dúvida, mapeamento de nomes e ordem invertida, layout NCHW
com logits, modelo ausente/inválido (3 saídas, sem `classe_positiva`, limiar inválido), os dois modos, bomba nunca acionada,
correção humana só com 2 classes, exportação e linha antiga com MODERADO no banco.
Com a **ResNet50 real** (`resnet50-224-20261116`): carrega, roda com o enquadramento (≈35–55 ms por foto na CPU deste ambiente)
e aparece no navegador, mas só com imagens sintéticas. **Não medidos:** acurácia em fotos reais e latência no Azure.
