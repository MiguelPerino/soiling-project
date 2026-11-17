# 04 · Firmware e hardware do ESP32

> **Estado:** o código em `firmware/esp32/` foi escrito e revisado, mas **não foi compilado nem rodado em hardware** neste projeto.
> Só a política da bomba (`pump_policy.h`) foi testada (no computador). As bibliotecas mudam de versão: espere ajustes na primeira compilação.

## Placa e limites
O projeto usa `esp32dev` no PlatformIO (normalmente ESP32‑WROOM‑32): ~520 KB de SRAM no total, **~320 KB utilizáveis** e **sem PSRAM**.
Não presuma que qualquer modelo caiba. Orçamento (a medir!): buffer do JPEG recebido 32 KB + imagem decodificada 25 KB (112×112 RGB565)
+ tensor arena (padrão 96 KB; as ativações do soilnet 2x somam ~67 KB, estimativa) + Wi‑Fi/pilha do sistema. O modelo em si (192 KB) fica na flash. Os buffers grandes são alocados no heap no boot (não como variáveis estáticas, para não estourar a RAM estática).
**Como provar que cabe:** grave, abra o Monitor Serial (115200) e leia `modelo ok. arena usada: X de Y bytes`. Se `AllocateTensors` falhar, aumente `TENSOR_ARENA_BYTES` (`config.h`) ou reduza a rede.

## Passo a passo
1. `cp firmware/esp32/src/secrets.example.h firmware/esp32/src/secrets.h` e preencha Wi‑Fi (e `DEVICE_KEY`, igual a `ESP32_KEY` do backend).
2. O modelo já está no repositório: `firmware/esp32/src/model_data.h` é o `models/esp32/model.tflite` (soilnet 2x) convertido, e o
   `config.h` já tem os valores dele. `scripts/test.sh` confere que os três batem (`backend/tests/test_esp32_model.py`).
3. Trocando de modelo: `02_DATASET_E_TREINO.md`, seção "Publicar um modelo novo do ESP32".
4. `cd firmware/esp32 && pio run -t upload && pio device monitor`. O Monitor mostra o IP: ponha em `ESP32_URL` do backend.
5. Teste do protocolo sem o front: `curl http://IP/` e `curl -X POST "http://IP/upload?pump=0" -H "Content-Type: image/jpeg" --data-binary @foto112.jpg`.

## Como o firmware funciona
`setup()`: **bomba desligada primeiro** → carrega o modelo → conecta ao Wi‑Fi → abre o servidor na porta 80.
`loop()`: `pumpTick()` (desliga a bomba pelo relógio, independente do HTTP) → atende um cliente. Em `POST /upload`: lê exatamente
`Content-Length` bytes (≤ 32 KB), decodifica o JPEG (JPEGDEC), exige INPUT_SIZE×INPUT_SIZE (112×112 no soilnet 2x), quantiza com a escala/zero‑point lidos do modelo,
`Invoke()`, calcula probabilidades, decide a bomba e responde JSON. O ESP32 fica ligado em espera; só calcula quando recebe foto.

## Segurança da bomba (inegociável)
| Regra | Onde |
| --- | --- |
| Estado inicial **desligado** (1ª instrução do `setup`) | `main.cpp` |
| Só `SEVERO` ("Precisa limpar") aciona; `LIMPO` nunca | `pump_policy.h` |
| Confiança < `CONF_THRESHOLD` (0,50 no soilnet 2x) → não aciona | `pump_policy.h` |
| Duração ≤ `PUMP_MAX_MS` (60 s), mesmo se o valor configurado for maior | `pump_policy.h` |
| Intervalo mínimo entre acionamentos (`PUMP_COOLDOWN_MS`, hoje 10 s para a bancada; **aumente em uso real**) | `pump_policy.h` |
| Bomba ocupada → recusa novo acionamento | `pump_policy.h` |
| Desligamento garantido pelo tempo, fora do fluxo HTTP | `pumpTick()` |
| Sem Wi‑Fi → bomba desligada | `loop()` |
| Requisição com `pump=0` nunca aciona (usado pelo backend sem chave de admin) | `handleClient` |
Ainda **faltam** (decisão de hardware): sensor de nível/ausência de água (rodar a bomba a seco a danifica), botão físico de parada e watchdog de hardware.

## Circuito
**Nunca ligue a bomba direto ao GPIO.** O pino só comanda um estágio de potência:
```
GPIO (PUMP_PIN) ─ 1 kΩ ─┬─ Gate  MOSFET nível lógico (ex.: IRLZ44N)      Fonte externa (+)──┬── Bomba ──┐
                        └─ 100 kΩ ─ GND (pull-down: bomba off no boot)                    │           │
GND do ESP32 ───────────────────── Source ────────────────────────── GND da fonte ──┐     Diodo 1N5819 │
                                                          Drain ───────────────────────┴────(catodo ao +, anodo ao Drain)
```
Valores são exemplos: dimensione pela tensão/corrente da **sua** bomba. Módulo de relé compatível com 3,3 V também serve. Diodo em antiparalelo
na bomba (carga indutiva) é obrigatório. **Alimentação da bomba separada** da do ESP32, com GND comum. Água longe da eletrônica; use caixa vedada.

## Checklist de bancada (nesta ordem)
1. Compila e conecta; `GET /` responde do computador (**teste de isolamento de clientes**: alguns hotspots de celular impedem que dispositivos se falem).
2. `PUMP_PIN=2` (LED da placa): `SEVERO` acende o LED por `PUMP_DURATION_MS` (2 s) e apaga; `LIMPO` não acende; 2º `SEVERO` dentro do intervalo mínimo é bloqueado.
3. Puxe o cabo Wi‑Fi/desligue o roteador com o LED aceso: deve apagar no tempo certo (pelo relógio).
4. Meça `arena_used_bytes`, tempo de inferência e `free_heap` com 20 fotos seguidas (sem queda contínua de heap).
5. Só então: MOSFET + bomba **sem água**, depois com água, com recipiente.
6. Compare a classificação do ESP32 com a do simulador para as mesmas fotos (devem coincidir, salvo arredondamento).

## Outra câmera?
Nesta versão a foto vem do celular/PC pelo backend. Uma ESP32‑CAM enviando fotos sozinha é outra arquitetura (o ESP32 seria cliente) e **não está implementada**.

## Modelo atual: soilnet 2x (`soilnet-2x-112-20261116`)
Treinado pelo time no notebook `ai-model/notebooks/3_treino_soilnet_esp32.ipynb` com o **dataset tratado 224** (fotos enquadradas).
Arquivos em `models/esp32/`; o firmware compila `src/model_data.h` (o mesmo `.tflite` em C).

| Item | Valor (do `models/esp32/model_card.json`) |
| --- | --- |
| Tarefa | binário: `NAOLIMPAR` (índice 0) → **LIMPO** "Não precisa limpar"; `LIMPAR` (índice 1, positiva) → **SEVERO** "Precisa limpar" |
| Entrada | 112×112 RGB, int8 (escala 1,0; zero-point −128; normalização dentro do modelo) |
| Pré-processamento | foto **enquadrada** (224, `preprocess.py` do notebook de tratamento) → 112 bilinear → JPEG 85 → RGB565. O backend faz tudo até o JPEG (`ESP32_FRAMING=panel`); o firmware decodifica em RGB565 |
| Tamanho | 135 834 parâmetros; `.tflite` de 196 224 bytes; ativações ~67 KB (estimativa) |
| Operadores | ADD, CONV_2D, DEPTHWISE_CONV_2D, FULLY_CONNECTED, MEAN, SOFTMAX (os mesmos do soilnet v1, que já rodou na placa) |
| Limiar | `DECISION_THRESHOLD` = `CONF_THRESHOLD` = 0,50: P(LIMPAR) ≥ 0,50 ⇒ SEVERO e a bomba pode acionar |
| Teste do time (196 fotos, int8) | acurácia 88,3% (IC95 83,7–92,3%), F1 macro 0,88, AUC 0,91; 6,9% das limpas acionariam, 17,0% das sujas seriam ignoradas |

**Como o sistema o enxerga:** o firmware responde com os nomes do sistema (`CLASS_NAMES` = `{"LIMPO","SEVERO"}` em `config.h`).
O backend usa `ESP32_CLASSES=LIMPO,SEVERO`, `ESP32_INPUT_SIZE=112`, `ESP32_FRAMING=panel` e `LOW_CONFIDENCE_THRESHOLD=0.50` (marca "revisar"
abaixo da mesma trava da bomba).

**Ao trocar de modelo**, revise em `config.h` tudo que está marcado `[MODELO]` (tamanho, número de classes, nomes, índice positivo, limiares,
versão), regenere o `model_data.h` e, no backend, `ESP32_INPUT_SIZE`/`ESP32_FRAMING`. `backend/tests/test_esp32_model.py` falha se o
`config.h`, o `model_data.h` e o `model_card.json` não baterem.

**O que foi e não foi verificado:** o `.tflite` roda no simulador (TFLite int8) com a mesma regra de decisão; o caminho completo
backend → simulador → bomba passa nos testes; `config.h` e `model_data.h` compilam com `g++` (só sintaxe C++, sem o SDK do ESP32).
O firmware com o soilnet 2x **não foi compilado no PlatformIO nem gravado na placa** neste ambiente: arena real, RAM livre e tempo de
inferência são desconhecidos. O soilnet v1 (mesmos operadores, metade dos parâmetros) rodou na placa em 12/11.

## Primeiro teste na placa (ESP32 via USB, LED azul)
1. **Wi‑Fi:** copie `src/secrets.example.h` para `src/secrets.h` e preencha `WIFI_SSID` e `WIFI_PASS`. O ESP32 só usa **2,4 GHz** com senha comum (WPA2‑PSK).
   Redes de faculdade costumam isolar os aparelhos ou exigir login: se não conectar, use o roteiro do celular (ponto de acesso, 2,4 GHz) e ligue o notebook nele.
2. **Gravar:** com o PlatformIO (extensão do VS Code ou linha de comando) na pasta `firmware/esp32`: `pio run -t upload` e depois `pio device monitor`
   (115200). Se travar em "Connecting...", segure o botão BOOT da placa até começar a gravar. O `model_data.h` (soilnet 2x) já está na pasta.
3. **Monitor serial:** deve aparecer `modelo ok. arena usada: N de 98304 bytes` e depois `IP: ...`. Anote os dois valores.
4. **Sem o backend:** `curl http://IP/` deve devolver `model_version: soilnet-2x-112-20261116`, `input_size: 112`, `classes: 2`.
5. **Com o sistema:** no notebook, `scripts/dev-esp32.sh IP` (ou `.\scripts\dev-esp32.ps1 IP`), abra `http://localhost:8000`, aba Analisar, "ESP32, na hora", permitir bomba.
6. **LED:** o pino da bomba (`PUMP_PIN=2` no `platformio.ini`) é o LED azul da placa. Uma foto SEVERO com confiança ≥ 0,50 acende o LED por 2 s (`PUMP_DURATION_MS`); depois há 10 s (`PUMP_COOLDOWN_MS`) de
   intervalo mínimo (um segundo acionamento antes disso é recusado de propósito, com o motivo na tela). `pump=0` nunca acende.
   Se a sua placa não tem LED no GPIO 2, ligue um LED com resistor nesse pino (ou troque `PUMP_PIN`).
7. **Se não compilar:** copie a mensagem de erro completa. A biblioteca `TensorFlowLite_ESP32 1.0.0` é de 2022 e pode rejeitar operadores de um `.tflite` gerado
   por um TensorFlow bem mais novo (erro típico: `Failed to get registration from op code` ou `AllocateTensors falhou`).
