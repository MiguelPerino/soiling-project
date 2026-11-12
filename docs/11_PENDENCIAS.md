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
| 13 | Recomendação de chuva: posição real do painel e limiares (1 mm / 10 mm são provisórios) | calibrar observando; testar com a API real |
| 12 | Mais de um ESP32 | não suportado nesta versão (um `ESP32_URL`) |
| 14 | **Modelo grande do servidor**: qual ResNet, arquivo ONNX, tamanho de entrada, normalização, saída (logits ou probabilidades), ordem das classes | pendente da equipe; o backend lê tudo da pasta `models/server` (`12_MODELO_NO_SERVIDOR.md`) |
| 15 | **Nomes das classes do ESP32**: o soilnet v1 é NAOLIMPAR/LIMPAR e o sistema mostra LIMPO/SEVERO | mapeado (NAOLIMPAR→LIMPO, LIMPAR→SEVERO), mas NAOLIMPAR inclui poeira leve; confirmar se "Painel limpo" na tela é o texto certo |
| 18 | **Soilnet v1 em hardware**: compila? cabe na RAM? `arena_used_bytes`? tempo de inferência? | não testado; o firmware foi adaptado mas **não compilado** (sem PlatformIO aqui) |
| 19 | **Limiar 0,41** do soilnet v1 (decisão e bomba) e `LOW_CONFIDENCE_THRESHOLD` do backend (0,60) | com 0,60 no backend, SEVERO entre 0,41 e 0,60 aciona a bomba e fica marcado "para revisar"; decidir se é isso |
| 20 | **Rótulos conflitantes no dataset** (`revisar_rotulos_conflitantes.csv` do soilnet v1) | o time precisa revisar; afeta a acurácia |
| 21 | Pré-processamento do treino vs. backend (redimensionamento, JPEG, RGB565) | o card diz `resize_mode: stretch`, qualidade 85, RGB565; confirmar que o método de redimensionamento do treino é bilinear como no backend |
| 16 | **Tamanho de entrada** dos dois modelos | configurável (`ESP32_INPUT_SIZE`, `SERVER_INPUT_SIZE`); definir quando o treino fechar |
| 17 | Latência do modelo grande no servidor local | não medida; depende da variante da ResNet e da CPU |
