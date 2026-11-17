# Firmware do ESP32

Passo a passo completo, riscos e checklist de bancada: [`docs/04_FIRMWARE_ESP32.md`](../../docs/04_FIRMWARE_ESP32.md).

Resumo:

```bash
cp src/secrets.example.h src/secrets.h                 # preencha Wi-Fi (e DEVICE_KEY, se usar)
pio run -t upload && pio device monitor                # o Monitor Serial mostra o IP e a RAM usada pelo modelo
g++ -std=c++17 -I src test/test_pump_policy.cpp -o /tmp/pp && /tmp/pp     # teste da política da bomba (no computador)
```

O modelo já vem pronto: `src/model_data.h` (versionado) é o `models/esp32/model.tflite` (soilnet 2x) convertido, e os
valores `[MODELO]` de `src/config.h` batem com o `models/esp32/model_card.json` (conferido por `backend/tests/test_esp32_model.py`).
Ao trocar de modelo: copie os arquivos novos para `models/esp32/`, regenere o header
(`python ai-model/conversion/tflite_to_header.py models/esp32/model.tflite firmware/esp32/src/model_data.h`, na raiz),
atualize os itens `[MODELO]` do `config.h` e rode `scripts/test.sh`.

Por padrão `PUMP_PIN=2` (LED da placa): valide TODA a lógica com o LED antes de ligar a bomba.
