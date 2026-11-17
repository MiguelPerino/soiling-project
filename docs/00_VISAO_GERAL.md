# 00 · Visão geral

## Objetivo
Dizer, a partir de uma fotografia, se um painel solar precisa ou não de limpeza e, quando necessário, acionar uma pequena bomba de
água para limpar. É uma **demonstração acadêmica funcional**, não um sistema industrial.

## Classes
São **duas classes**. O código vai na API, no banco e no protocolo do ESP32; o texto é o que a tela mostra.

| Código | Na tela | Nos modelos | Ação |
| --- | --- | --- | --- |
| `LIMPO` | Não precisa limpar | `NaoLimpar` / `NAOLIMPAR` | nenhuma |
| `SEVERO` | Precisa limpar | `Limpar` / `LIMPAR` (classe positiva) | ESP32: acionar a bomba se a confiança ≥ limiar. Servidor: só informa |

Os dois modelos decidem por **limiar** sobre P(Limpar), não pela classe de maior probabilidade (ESP32: 0,50; servidor: 0,19).
Antes dos dois modelos, a foto é **enquadrada** (placa recortada) pelo mesmo código que tratou o dataset de treino.

`confidence` (0–1) é o quanto a rede "tem certeza" da classe. **Não é percentual de sujeira.** O modelo não mede quantidade de sujeira.

## Decisões de arquitetura (do documento de arquitetura da equipe)
- Dois modos: inferência **no ESP32** (decide a bomba; o backend só encaminha e registra) ou **no servidor** com um modelo grande opcional (ONNX; nunca aciona a bomba). Veja `12_MODELO_NO_SERVIDOR.md`.
- Comunicação **HTTP na rede Wi‑Fi local**; sem MQTT.
- O ESP32 é um **servidor HTTP**: `GET /` (online?) e `POST /upload` (foto).
- Imagem redimensionada no navegador; no ESP32 fica só na RAM, durante a análise.
- Banco: PostgreSQL, tabela `analyses`; imagens em **arquivos**, banco guarda o caminho.
- Front: React + TypeScript + Tailwind + Recharts. Back: Python + FastAPI.

## Decisões nossas (e por quê)
| Decisão | Motivo |
| --- | --- |
| Rede pequena no ESP32 (soilnet 2x: 136 mil parâmetros, entrada 112×112, int8, 192 KB) | `esp32dev` não tem PSRAM; ~320 KB de RAM utilizável |
| Treino em notebooks (Keras → TFLite int8 no ESP32; PyTorch → ONNX no servidor) | caminho nativo do TFLite Micro; ResNet pré-treinada para o servidor |
| Mesmo enquadramento no treino e na inferência | o modelo só vê, em uso, fotos preparadas como as do treino |
| Normalização dentro do modelo | o firmware só entrega pixels e quantiza com a escala do tensor; menos chance de divergir do treino |
| Política da bomba no firmware | segurança física não pode depender de rede nem do servidor |
| Simulador do ESP32 | testar e ensaiar sem hardware; "imagem de reserva" na apresentação |
| Gemini via backend, com plano B | a chave não vai ao navegador; a demo funciona sem internet |
| Recomendação de chuva (Open‑Meteo) só na tela | ajuda a decidir se compensa limpar; previsão erra e precisa de internet, então **nunca** comanda a bomba |
| Terraform só opcional | um ESP32 na sua rede Wi‑Fi não é alcançável por um servidor na nuvem (ver `08_DEPLOY.md`) |

## Glossário
**Soiling**: acúmulo de sujeira no painel. **TFLite Micro**: runtime de redes neurais para microcontroladores. **int8**: pesos e
ativações em inteiros de 8 bits (modelo ~4× menor). **Tensor arena**: bloco de RAM que o TFLite Micro usa para os cálculos.
**Cooldown**: intervalo mínimo entre dois acionamentos da bomba.
