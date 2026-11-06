# 11 · Pendências e decisões em aberto

| # | Item | Estado / recomendação |
| --- | --- | --- |
| 1 | **Mapeamento das classes** do Roboflow (Clean/Dusty/Soiled → LIMPO/MODERADO/SEVERO) | suposição; conferir imagens e ajustar `--class-map` |
| 2 | **Tipo do projeto Roboflow** (classificação ou detecção?) e formato de export | não confirmado; precisa ser classificação |
| 3 | **Treino com dados reais** e acurácia | pendente |
| 4 | **Modelo cabe no ESP32?** (arena, velocidade, heap) | pendente de teste em hardware; ver `04_` |
| 5 | **Câmera**: foto vem do celular/PC (arquitetura atual) ou ESP32‑CAM? | decidido: celular/PC; ESP32‑CAM seria outra arquitetura |
| 6 | **Bomba**: modelo, tensão, vazão; sensor de nível de água; botão de parada | pendente; definir antes de ligar |
| 7 | **Parâmetros da bomba** (duração, cooldown) | padrão 5 s / 60 s; ajustar com a bomba real |
| 8 | **Gemini**: modelo, limites e termos do plano gratuito | pendente; sem padrão de propósito |
| 9 | **Nuvem**: AWS por padrão; realmente precisa? | local é o recomendado; Terraform é opcional (limite do ESP32 na LAN) |
| 10 | Migrações (Alembic), TLS, login | fora do escopo do protótipo |
| 11 | Limiar de confiança 0,60 | ponto de partida; calibrar com `metrics.json` |
| 12 | Mais de um ESP32 | não suportado nesta versão (um `ESP32_URL`) |
