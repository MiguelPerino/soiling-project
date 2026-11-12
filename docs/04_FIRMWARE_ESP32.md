# 04 · Firmware e hardware do ESP32

> **Estado:** o código em `firmware/esp32/` foi escrito e revisado, mas **não foi compilado nem rodado em hardware** neste projeto.
> Só a política da bomba (`pump_policy.h`) foi testada (no computador). As bibliotecas mudam de versão: espere ajustes na primeira compilação.

## Placa e limites
O projeto usa `esp32dev` no PlatformIO (normalmente ESP32‑WROOM‑32): ~520 KB de SRAM no total, **~320 KB utilizáveis** e **sem PSRAM**.
Não presuma que qualquer modelo caiba. Orçamento (a medir!): buffer do JPEG recebido 32 KB + imagem decodificada 25 KB (112×112 RGB565)
+ tensor arena (padrão 96 KB; o soilnet v1 estima ~69 KB) + Wi‑Fi/pilha do sistema. O modelo em si (114 KB) fica na flash. Os buffers grandes são alocados no heap no boot (não como variáveis estáticas, para não estourar a RAM estática).
**Como provar que cabe:** grave, abra o Monitor Serial (115200) e leia `modelo ok. arena usada: X de Y bytes`. Se `AllocateTensors` falhar, aumente `TENSOR_ARENA_BYTES` (`config.h`) ou reduza a rede.

## Passo a passo
1. `cp firmware/esp32/src/secrets.example.h firmware/esp32/src/secrets.h` e preencha Wi‑Fi (e `DEVICE_KEY`, igual a `ESP32_KEY` do backend).
2. Treine o modelo (`02_DATASET_E_TREINO.md`) e gere `model_data.h`:
   `python ai-model/conversion/tflite_to_header.py ai-model/models/current/model.tflite firmware/esp32/src/model_data.h`
3. Confira que `INPUT_SIZE` em `config.h` = `input_size` do `model_card.json`.
4. `cd firmware/esp32 && pio run -t upload && pio device monitor`. O Monitor mostra o IP: ponha em `ESP32_URL` do backend.
5. Teste do protocolo sem o front: `curl http://IP/` e `curl -X POST "http://IP/upload?pump=0" -H "Content-Type: image/jpeg" --data-binary @foto112.jpg`.

## Como o firmware funciona
`setup()`: **bomba desligada primeiro** → carrega o modelo → conecta ao Wi‑Fi → abre o servidor na porta 80.
`loop()`: `pumpTick()` (desliga a bomba pelo relógio, independente do HTTP) → atende um cliente. Em `POST /upload`: lê exatamente
`Content-Length` bytes (≤ 32 KB), decodifica o JPEG (JPEGDEC), exige INPUT_SIZE×INPUT_SIZE (112×112 no soilnet v1), quantiza com a escala/zero‑point lidos do modelo,
`Invoke()`, calcula probabilidades, decide a bomba e responde JSON. O ESP32 fica ligado em espera; só calcula quando recebe foto.

## Segurança da bomba (inegociável)
| Regra | Onde |
| --- | --- |
| Estado inicial **desligado** (1ª instrução do `setup`) | `main.cpp` |
| Só `SEVERO` aciona; `MODERADO`/`LIMPO` nunca | `pump_policy.h` |
| Confiança < 0,60 → não aciona | `pump_policy.h` |
| Duração ≤ `PUMP_MAX_MS` (60 s), mesmo se o valor configurado for maior | `pump_policy.h` |
| Intervalo mínimo entre acionamentos (`PUMP_COOLDOWN_MS`, padrão 60 s; **aumente em uso real**) | `pump_policy.h` |
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
2. `PUMP_PIN=2` (LED da placa): `SEVERO` acende o LED por 5 s e apaga; `LIMPO`/`MODERADO` não acendem; 2º `SEVERO` seguido é bloqueado.
3. Puxe o cabo Wi‑Fi/desligue o roteador com o LED aceso: deve apagar no tempo certo (pelo relógio).
4. Meça `arena_used_bytes`, tempo de inferência e `free_heap` com 20 fotos seguidas (sem queda contínua de heap).
5. Só então: MOSFET + bomba **sem água**, depois com água, com recipiente.
6. Compare a classificação do ESP32 com a do simulador para as mesmas fotos (devem coincidir, salvo arredondamento).

## Outra câmera?
Nesta versão a foto vem do celular/PC pelo backend. Uma ESP32‑CAM enviando fotos sozinha é outra arquitetura (o ESP32 seria cliente) e **não está implementada**.

## Modelo soilnet v1 (primeiro modelo treinado pelo time)
Recebido em 10/11/2026 (`soilnet-112-20261110`). Os arquivos de implantação estão em `ai-model/models/current/` (`model.tflite`,
`model_card.json`, `labels.json`) e o `model_data.h` já está em `firmware/esp32/src/`. Os arquivos de treino (SavedModel, Keras,
curvas, partição) ficam com o time.

| Item | Valor (do `model_card.json`) |
| --- | --- |
| Tarefa | binário: `NAOLIMPAR` (índice 0) e `LIMPAR` (índice 1) |
| Entrada | 112×112 RGB, int8 (escala 1,0; zero-point −128; a normalização está dentro do modelo), esticada, JPEG qualidade 85, treinado com RGB565 |
| Tamanho | 67 250 parâmetros; `.tflite` de 114 008 bytes; arena estimada em ~69 KB |
| Operadores | ADD, CONV_2D, DEPTHWISE_CONV_2D, FULLY_CONNECTED, MEAN, SOFTMAX |
| Limiar | `limiar_limpar` = 0,41: P(LIMPAR) ≥ 0,41 ⇒ LIMPAR (não é o argmax) |
| Dados | 388 treino, 87 validação, 87 teste; F1 macro (validação) 0,862 em float e em int8; AUC 0,923 |

**Como o sistema o enxerga:** o firmware responde com os nomes do sistema, `NAOLIMPAR → LIMPO` e `LIMPAR → SEVERO` (vetor `CLASS_NAMES` em
`config.h`). A bomba só aciona na classe positiva (`POSITIVE_CLASS`), com `CONF_THRESHOLD` = 0,41. O backend usa `ESP32_CLASSES=LIMPO,SEVERO`
e `ESP32_INPUT_SIZE=112`. **Atenção:** NAOLIMPAR inclui poeira leve; na tela aparece como "LIMPO".

**Ao trocar de modelo**, revise em `config.h` tudo que está marcado `[MODELO]` (tamanho, número de classes, nomes, índice positivo, limiares,
versão), o `model_data.h` e, no backend, `ESP32_INPUT_SIZE` e `ESP32_CLASSES`.

**O que foi e não foi verificado:** o `.tflite` roda no simulador (TFLite int8) com a mesma regra de decisão e testes automáticos da lógica
(`firmware/esp32/test/`) passam em C++. O firmware **não foi compilado** (sem PlatformIO neste ambiente) nem rodado no ESP32: arena real,
RAM disponível e tempo de inferência são desconhecidos. A acurácia vem das métricas do time, não foi remedida aqui.

## Primeiro teste na placa (ESP32 via USB, LED azul)
1. **Wi‑Fi:** copie `src/secrets.example.h` para `src/secrets.h` e preencha `WIFI_SSID` e `WIFI_PASS`. O ESP32 só usa **2,4 GHz** com senha comum (WPA2‑PSK).
   Redes de faculdade costumam isolar os aparelhos ou exigir login: se não conectar, use o roteiro do celular (ponto de acesso, 2,4 GHz) e ligue o notebook nele.
2. **Gravar:** com o PlatformIO (extensão do VS Code ou linha de comando) na pasta `firmware/esp32`: `pio run -t upload` e depois `pio device monitor`
   (115200). Se travar em "Connecting...", segure o botão BOOT da placa até começar a gravar. O `model_data.h` (soilnet v1) já está na pasta.
3. **Monitor serial:** deve aparecer `modelo ok. arena usada: N de 98304 bytes` e depois `IP: ...`. Anote os dois valores.
4. **Sem o backend:** `curl http://IP/` deve devolver `model_version: soilnet-112-20261110`, `input_size: 112`, `classes: 2`.
5. **Com o sistema:** no notebook, `scripts/dev-esp32.sh IP` (ou `.\scripts\dev-esp32.ps1 IP`), abra `http://localhost:8000`, aba Analisar, "ESP32, na hora", permitir bomba.
6. **LED:** o pino da bomba (`PUMP_PIN=2` no `platformio.ini`) é o LED azul da placa. Uma foto SEVERO com confiança ≥ 0,41 acende o LED por 5 s; depois há 60 s de
   intervalo mínimo (um segundo acionamento antes disso é recusado de propósito, com o motivo na tela). `pump=0` nunca acende.
   Se a sua placa não tem LED no GPIO 2, ligue um LED com resistor nesse pino (ou troque `PUMP_PIN`).
7. **Se não compilar:** copie a mensagem de erro completa. A biblioteca `TensorFlowLite_ESP32 1.0.0` é de 2022 e pode rejeitar operadores de um `.tflite` gerado
   por um TensorFlow bem mais novo (erro típico: `Failed to get registration from op code` ou `AllocateTensors falhou`).
