# 07 · API (resumo; a versão interativa está em `/docs` com o backend no ar)

| Método | Rota | Auth | Descrição |
| --- | --- | --- | --- |
| GET | `/api/health` | — | banco, ESP32 configurado, Gemini, admin protegido |
| GET | `/api/config` | — | `input_size`, `jpeg_quality`, `max_upload_mb`, limiar, flags (o front usa para preparar a foto) |
| GET | `/api/devices/status` | — | ESP32 online? (`online`, `latency_ms`, `info`) — nunca dá erro, devolve `online:false` |
| POST | `/api/analyze` | `X-API-Key` só para a bomba | multipart: `file`, `pump` (padrão true). Devolve `{analise, bomba_bloqueada_por_falta_de_chave}` |
| GET | `/api/analyses` | — | filtros: `labels` (repetível), `needs_review`, `cleaning_activated`, `since`, `until`, `text`, `limit` (≤200), `offset` |
| GET | `/api/analyses/{id}` | — | uma análise |
| GET | `/api/analyses/{id}/image` | — | o JPEG |
| PATCH | `/api/analyses/{id}/label` | admin | `{"label": "SEVERO"}` ou `null` para remover a correção |
| DELETE | `/api/analyses/{id}` | admin | apaga linha e arquivo |
| GET | `/api/stats` | — | totais, por rótulo, revisão, limpezas, série diária (14 dias, fuso America/Sao_Paulo) |
| POST | `/api/assistant/ask` | — | `{"question": "..."}` → filtro, resultados e resumo |
| POST | `/api/assistant/explain` | — | dúvida geral (IA) |

Códigos de erro de `/api/analyze`: 400 vazio · 413 grande · 422 não é imagem · 502 ESP32 respondeu errado · 503 ESP32 não configurado · 504 ESP32 não respondeu.
`final_label` = `human_label` se existir, senão `classification`. Filtros e estatísticas usam `final_label`.
Quem admin: sem `ADMIN_API_KEY` configurada **tudo é aberto** (só para teste local).
