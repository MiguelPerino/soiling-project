#pragma once
// Parâmetros do firmware. Mantenha em sincronia com models/esp32/model_card.json (o modelo gravado em model_data.h)
// e com docs/05_PROTOCOLO_ESP32.md. Ao trocar de modelo, confira TODOS os itens marcados com [MODELO]
// (backend/tests/test_esp32_model.py confere automaticamente se config.h, model_data.h e o model_card.json batem).
#include <cstddef>
#include <cstdint>

// ---- [MODELO] soilnet-2x-112-20261116 (binário, treinado com o dataset tratado 224: notebook treino_esp32_dataset224) ----
constexpr int      INPUT_SIZE          = 112;       // model_card.json: input_size
constexpr int      NUM_CLASSES         = 2;         // número de saídas do modelo (labels.json)
// Saída i do modelo -> rótulo do SISTEMA, na ordem do labels.json do modelo (aqui: NAOLIMPAR -> LIMPO, LIMPAR -> SEVERO).
// O sistema tem só duas classes: LIMPO ("Não precisa limpar") e SEVERO ("Precisa limpar").
static const char *const CLASS_NAMES[NUM_CLASSES] = {"LIMPO", "SEVERO"};
constexpr int      POSITIVE_CLASS      = 1;         // índice da classe que aciona a bomba (model_card.json: positive_label = LIMPAR)
constexpr float    DECISION_THRESHOLD  = 0.50f;     // P(positiva) >= isto => classe positiva (model_card.json: limiar_limpar)
constexpr float    CONF_THRESHOLD      = 0.50f;     // a bomba exige confiança >= isto (model_card.json: low_confidence_threshold)
#define MODEL_VERSION "soilnet-2x-112-20261116"     // devolvido ao backend; igual ao "version" do model_card.json
static_assert(NUM_CLASSES == 2, "o sistema é binário: LIMPO e SEVERO");

// ---- memória ----
constexpr size_t   MAX_BODY_BYTES      = 32 * 1024; // buffer do JPEG recebido; acima disso: HTTP 413
constexpr size_t   TENSOR_ARENA_BYTES  = 96 * 1024; // estimativa das ativações do soilnet 2x: ~67 KB; o firmware imprime arena_used_bytes() no boot: ajuste depois de medir

// ---- bomba (valores de segurança; o backend também limita a 60 s) ----
constexpr uint32_t PUMP_DURATION_MS    = 2000;      // quanto tempo a bomba fica ligada em cada acionamento
constexpr uint32_t PUMP_MAX_MS         = 60000;     // teto absoluto, mesmo que o valor acima seja alterado por engano
constexpr uint32_t PUMP_COOLDOWN_MS    = 10000;     // intervalo mínimo entre acionamentos (aumente para uso real)
