#pragma once
// Escolha da classe a partir das probabilidades do modelo. C++ puro (sem Arduino) para ser testado no computador.
//
// Modelo binário (2 saídas): vale o LIMIAR DE OPERAÇÃO na classe positiva (a que aciona a bomba), como no model_card.json
// ("limiar_limpar"): P(positiva) >= limiar => classe positiva; senão, a outra. Não é o argmax: com limiar 0,41 uma foto com
// P(positiva)=0,45 é positiva mesmo que a outra classe tenha 0,55.
// Mais de 2 saídas: argmax.
struct Pick {
  int   index;
  float confidence;   // probabilidade da classe escolhida
};

inline Pick pickClass(const float *probs, int n, int positive, float threshold) {
  if (n == 2) {
    const int neg = 1 - positive;
    return probs[positive] >= threshold ? Pick{positive, probs[positive]} : Pick{neg, probs[neg]};
  }
  int best = 0;
  for (int i = 1; i < n; i++) if (probs[i] > probs[best]) best = i;
  return Pick{best, probs[best]};
}
