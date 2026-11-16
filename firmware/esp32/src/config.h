#pragma once
// Parâmetros do firmware. Mantenha em sincronia com o model_card.json do modelo gravado (ai-model/models/current/)
// e com docs/05_PROTOCOLO_ESP32.md. Ao trocar de modelo, confira TODOS os itens marcados com [MODELO].
#include <cstddef>
#include <cstdint>

// ---- [MODELO] soilnet-112-20261110 (binário) ----
constexpr int      INPUT_SIZE          = 112;       // model_card.json: input_size
constexpr int      NUM_CLASSES         = 2;         // número de saídas do modelo (labels.json)
// Saída i do modelo -> rótulo do SISTEMA, na ordem do labels.json do modelo (aqui: NAOLIMPAR -> LIMPO, LIMPAR -> SEVERO).
// O backend (ESP32_CLASSES) e o front só conhecem LIMPO, MODERADO e SEVERO.
static const char *const CLASS_NAMES[NUM_CLASSES] = {"LIMPO", "SEVERO"};
constexpr int      POSITIVE_CLASS      = 1;         // índice da classe que aciona a bomba (model_card.json: positive_label = LIMPAR)
constexpr float    DECISION_THRESHOLD  = 0.41f;     // P(positiva) >= isto => classe positiva (model_card.json: limiar_limpar)
constexpr float    CONF_THRESHOLD      = 0.41f;     // a bomba exige confiança >= isto (igual ao limiar acima; subir deixa a bomba mais conservadora)
#define MODEL_VERSION "soilnet-112-20261110"        // devolvido ao backend; igual ao "version" do model_card.json

// ---- memória ----
constexpr size_t   MAX_BODY_BYTES      = 32 * 1024; // buffer do JPEG recebido; acima disso: HTTP 413
constexpr size_t   TENSOR_ARENA_BYTES  = 96 * 1024; // o model_card estima ~69 KB; o firmware imprime arena_used_bytes() no boot: ajuste depois de medir

// ---- bomba (valores de segurança; o backend também limita a 60 s) ----
constexpr uint32_t PUMP_DURATION_MS    = 2000;      // quanto tempo a bomba fica ligada em cada acionamento
constexpr uint32_t PUMP_MAX_MS         = 60000;     // teto absoluto, mesmo que o valor acima seja alterado por engano
constexpr uint32_t PUMP_COOLDOWN_MS    = 10000;     // intervalo mínimo entre acionamentos (aumente para uso real)
