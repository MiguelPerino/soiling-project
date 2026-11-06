# 06 · Front-end e assistente (Gemini)

## Front
React 18 + TypeScript + Tailwind 3 + Recharts, Vite. Código em `frontend/src`; `api.ts` é a única porta para a API.
Desenvolvimento: `cd frontend && npm run dev` (http://localhost:5173, `/api` vai para `:8000`). Produção: `npm run build` → `frontend/dist`,
servido pelo FastAPI (e pelo Docker).

| Aba | Faz |
| --- | --- |
| Analisar | escolhe/tira foto, reduz no navegador para o tamanho do modelo, envia, mostra classe, probabilidades, bomba, tempos |
| Histórico | cards com filtros (classe, para revisar, bomba acionada), detalhe, **correção humana**, reanálise, apagar |
| Painel | totais, limpezas acionadas, tempo de bomba, para revisar, confiança média, gráfico por dia (atualiza a cada 10 s) |
| Assistente | busca em português nas análises ou dúvida geral sobre soiling |

Topo: indicador do ESP32 (consulta `/api/devices/status` a cada 5 s; mostra "simulador" quando for o simulador) e botão **Admin** (chave guardada só na aba).

**Câmera:** usamos `<input type="file" capture="environment">`, que abre o app de câmera do celular e **não exige HTTPS** (ao contrário de `getUserMedia`).
Testado só no Chromium desktop e emulação de celular; teste no aparelho que será usado na apresentação.

**Reanalisar** (no detalhe de uma análise) reenvia uma foto já guardada: é a "imagem de reserva" se a câmera falhar. Cria uma nova análise, com a bomba desativada.

## Assistente
Rotas `POST /api/assistant/ask` (buscar) e `/explain` (dúvida geral). Fluxo de `ask`:
1. **Gemini** converte a pergunta em um filtro JSON (classes, período, revisão, bomba…). O JSON é **validado** (pydantic); inválido → regras em português.
2. **O banco** busca e conta. A IA nunca vê fotos nem escolhe análises.
3. A IA recebe só **contagens agregadas** e redige até 4 frases. **Todo número do texto precisa existir nos dados enviados**; senão descartamos e usamos um texto determinístico.
4. A resposta traz `fonte` (`gemini` ou `regras`) e o front mostra qual foi usada.
`explain` é conhecimento geral da IA, marcado como tal, sem números de estudos.

Configuração: `GEMINI_API_KEY` e `GEMINI_MODEL` (sem padrão: nomes mudam; veja a lista atual em <https://ai.google.dev/gemini-api/docs/models>).
Sem as duas, tudo funciona por regras. **Não testado contra a API real**: antes da apresentação, faça uma pergunta e confirme `fonte: gemini`.
Verifique limites e uso de dados do plano gratuito na documentação do Google (não conseguimos abrir a página de limites ao construir isto).
Precisa de internet; sem internet o plano B entra sozinho.
