# 01 · Arquitetura

## Fluxo (1 análise)
1. Usuário abre o front (celular ou PC) e tira/escolhe a foto.
2. O **front** reduz a imagem para `INPUT_SIZE×INPUT_SIZE` (padrão 96, esticada) e comprime em JPEG (`/api/config` informa os valores).
3. `POST /api/analyze` (multipart, campo `file`, campo `pump`).
4. O **backend** valida o arquivo (≤ `MAX_UPLOAD_MB`, é imagem), refaz o redimensionamento se necessário e envia ao ESP32:
   `POST {ESP32_URL}/upload?pump=0|1` com o JPEG no corpo.
5. O **ESP32** decodifica, quantiza, roda a rede, aplica a política da bomba e responde JSON (`05_PROTOCOLO_ESP32.md`).
6. O backend valida a resposta, grava o JPEG em `STORAGE_DIR` e uma linha em `analyses` (se o ESP32 falhar, **nada** é gravado).
7. O front mostra classe, confiança, se a bomba foi acionada, tempos; histórico e painel se atualizam.

## Componentes
```
frontend (React) ── /api/* ──▶ backend (FastAPI)
                                 ├─ services/analysis.py   prepara imagem, orquestra
                                 ├─ services/esp32.py      cliente HTTP do ESP32 (valida a resposta)
                                 ├─ services/storage.py    arquivos (anti path traversal, gravação atômica)
                                 ├─ database/repository.py SQLAlchemy (PostgreSQL / SQLite)
                                 └─ services/assistant/    Gemini + plano B por regras
firmware (ESP32) ◀── HTTP local ── backend
```

## Falhas previstas
| Situação | Resposta da API | Efeito |
| --- | --- | --- |
| `ESP32_URL` vazio | 503 | nada gravado |
| ESP32 não responde (Wi‑Fi, IP, timeout) | 504 | nada gravado |
| ESP32 responde erro ou JSON fora do contrato (classe inventada, bomba > 60 s) | 502 | nada gravado |
| Arquivo não é imagem / formato não suportado | 422 | nada gravado |
| Arquivo > limite | 413 | nada gravado |
| Sem `X-API-Key` com `pump=true` e chave configurada | 200, mas enviado `pump=0` e o front avisa | análise gravada, bomba bloqueada |
| Banco falha depois de gravar o arquivo | 500 | arquivo removido (sem órfão) |

## Concorrência
O ESP32 tem **um buffer só**: atende uma foto por vez. O backend espera a resposta na mesma requisição (timeout `ESP32_TIMEOUT_S`, 30 s).
Para a demonstração isso basta; se a inferência demorar demais, evoluir para processamento assíncrono com id de tarefa (não implementado).

## Segurança (nível protótipo)
Rede local confiável. `ADMIN_API_KEY` protege: acionar a bomba, corrigir rótulo, apagar. `ESP32_KEY` (opcional) é um segredo
compartilhado no cabeçalho `X-Device-Key`. **Não há TLS, nem login de usuários, nem limitação de taxa.** Não exponha à internet sem um proxy com HTTPS.
