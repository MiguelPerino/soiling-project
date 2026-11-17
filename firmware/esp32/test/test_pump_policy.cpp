// Teste nativo da política da bomba: g++ -std=c++17 -I src test/test_pump_policy.cpp && ./a.out   (ou: pio test -e native)
#include <cassert>
#include <cstdio>
#include "pump_policy.h"
#include "decision.h"

int main() {
  PumpPolicy p{0.60f, 5000, 60000, 60000};
  assert(!p.decide(Label::LIMPO, 0.99f, true, 1000).activate);
  assert(!p.decide(Label::SEVERO, 0.59f, true, 1000).activate);          // baixa confiança
  assert(!p.decide(Label::SEVERO, 0.99f, false, 1000).activate);         // pump=0
  auto d = p.decide(Label::SEVERO, 0.90f, true, 1000);                   // logo após o boot: deve acionar
  assert(d.activate && d.duration_ms == 5000);
  p.started();
  assert(!p.decide(Label::SEVERO, 0.99f, true, 2000).activate);          // ocupada
  p.finished(6000);
  assert(!p.decide(Label::SEVERO, 0.99f, true, 30000).activate);         // cooldown
  assert(p.decide(Label::SEVERO, 0.99f, true, 66001).activate);          // passou o intervalo
  PumpPolicy big{0.6f, 999999, 60000, 1000};
  assert(big.decide(Label::SEVERO, 0.9f, true, 0).duration_ms == 60000); // teto de segurança
  PumpPolicy wrap{0.6f, 5000, 60000, 60000};
  wrap.finished(0xFFFFFF00u);                                            // virada do millis() (~49 dias)
  assert(!wrap.decide(Label::SEVERO, 0.9f, true, 0xFFFFFF00u + 1000).activate);
  assert(wrap.decide(Label::SEVERO, 0.9f, true, 0xFFFFFF00u + 61000).activate);
  // escolha da classe (decision.h): binário usa o limiar de operação na classe positiva, não o argmax
  { float p[2] = {0.55f, 0.45f};
    Pick k = pickClass(p, 2, 1, 0.41f);
    assert(k.index == 1 && k.confidence == 0.45f); }                                   // 0,45 >= 0,41: positiva mesmo perdendo no argmax
  { float p[2] = {0.61f, 0.39f};
    Pick k = pickClass(p, 2, 1, 0.41f);
    assert(k.index == 0 && k.confidence == 0.61f); }                                   // abaixo do limiar: negativa, confiança da negativa
  { float p[2] = {0.59f, 0.41f};
    assert(pickClass(p, 2, 1, 0.41f).index == 1); }                                    // no limiar: positiva
  { float p[2] = {0.2f, 0.8f};
    assert(pickClass(p, 2, 0, 0.41f).index == 1); }                                    // positiva = índice 0: P(0)=0,2 < 0,41 => escolhe o 1
  { float p[3] = {0.2f, 0.5f, 0.3f};
    assert(pickClass(p, 3, 2, 0.41f).index == 1); }                                    // 3 classes: argmax
  // modelo atual (soilnet 2x): limiar de decisão e da bomba = 0,50
  { PumpPolicy q{0.50f, 2000, 60000, 10000};
    float hi[2] = {0.30f, 0.70f}, lo[2] = {0.51f, 0.49f};
    Pick a = pickClass(hi, 2, 1, 0.50f), b = pickClass(lo, 2, 1, 0.50f);
    assert(a.index == 1 && q.decide(Label::SEVERO, a.confidence, true, 1000).activate);
    assert(b.index == 0 && !q.decide(Label::LIMPO, b.confidence, true, 1000).activate); }
  // com o limiar da bomba igual ao de decisão, a foto positiva limítrofe aciona
  { PumpPolicy q{0.41f, 5000, 60000, 60000};
    float p[2] = {0.55f, 0.45f};
    Pick k = pickClass(p, 2, 1, 0.41f);
    assert(q.decide(Label::SEVERO, k.confidence, true, 1000).activate); }
  std::puts("pump_policy + decision: ok");
  return 0;
}
