---
name: esp32-firmware
description: Firmware do ESP32 (PlatformIO, TFLite Micro, JPEGDEC, bomba) e checklist de bancada. Use ao compilar, gravar, depurar memória ou mexer na segurança da bomba.
---
# Firmware (firmware/esp32/)

Com o soilnet v1 o firmware compilou e rodou na placa (12/11). Com o **soilnet 2x** atual (`models/esp32`, 192 KB, limiar 0,50) só foi
compilado em g++ (sem o SDK do ESP32): grave e confira `arena usada` no Monitor Serial.

Passos: `secrets.h` (copie do exemplo) → `pio run -t upload` → `pio device monitor` (115200): lê o IP e `arena usada`.
`src/model_data.h` já está no repositório (é `models/esp32/model.tflite` convertido). Trocar de modelo: skill `train-model`.

Regras de segurança (não enfraqueça): pino da bomba **desligado na 1ª instrução do `setup`**; só SEVERO; confiança ≥ `CONF_THRESHOLD`; duração ≤ 60 s; cooldown; bomba ocupada recusa; desligamento por relógio em `pumpTick()` (fora do HTTP); sem Wi‑Fi → desliga; `pump=0` nunca aciona.
Qualquer mudança na política vai **primeiro** em `pump_policy.h` + `test/test_pump_policy.cpp` (`g++ -std=c++17 -I src test/test_pump_policy.cpp`), depois no simulador (`tools/esp32_simulator/server.py`).

Memória (esp32dev, sem PSRAM): buffer JPEG 32 KB + frame 25 KB (112×112) + arena (96 KB) + Wi‑Fi. Se `AllocateTensors` falhar: aumente `TENSOR_ARENA_BYTES` ou reduza a rede. Troque `AllOpsResolver` por `MicroMutableOpResolver` com os operadores do `model_card.json` para economizar flash.
Consistência: `INPUT_SIZE`, `DECISION_THRESHOLD`, `CONF_THRESHOLD`, `POSITIVE_CLASS`, `CLASS_NAMES` e `MODEL_VERSION` em `config.h` devem bater com
`models/esp32/model_card.json`, e `model_data.h` com o `.tflite`: `backend/tests/test_esp32_model.py` confere. Classes: só LIMPO e SEVERO (`static_assert`).
A foto chega já enquadrada pelo backend (`ESP32_FRAMING=panel`); o firmware só decodifica em RGB565 e quantiza.
Circuito: nunca bomba direto no GPIO; MOSFET/relé + diodo + fonte separada com GND comum. Valide com LED (`PUMP_PIN=2`) antes. Detalhes e checklist: `docs/04_FIRMWARE_ESP32.md`.
