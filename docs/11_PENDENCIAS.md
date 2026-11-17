# 11 · Pendências e decisões em aberto

| # | Item | Estado / recomendação |
| --- | --- | --- |
| 1 | **Classes**: o sistema é binário (Não precisa limpar / Precisa limpar) | **decidido** em 17/11; MODERADO não existe mais em nenhuma parte |
| 2 | **Dataset** bruto e tratado (`Datasetv6_224`) | fora do repositório, com a equipe; tratamento e treinos em `ai-model/notebooks/` |
| 3 | **Acurácia com fotos reais pelo sistema** | pendente: as métricas são as do teste dos notebooks (soilnet 2x 88,3%; ResNet50 95,3%) |
| 4 | **soilnet 2x na placa**: compila? `arena_used_bytes`, `free_heap`, `inference_ms` | pendente: gravar e anotar o Monitor Serial. Mesmos operadores do v1 (que rodou em 12/11) e ativações estimadas iguais (~67 KB); o `.tflite` cresceu de 114 para 192 KB de flash |
| 5 | **Câmera**: foto vem do celular/PC (arquitetura atual) ou ESP32‑CAM? | decidido: celular/PC; ESP32‑CAM seria outra arquitetura |
| 6 | **Bomba**: modelo, tensão, vazão; sensor de nível de água; botão de parada | pendente; definir antes de ligar |
| 7 | **Parâmetros da bomba** (duração, intervalo mínimo) | hoje 2 s / 10 s (`config.h`, valores de bancada); ajustar com a bomba real |
| 8 | **Gemini**: modelo, limites e termos do plano gratuito | pendente; sem padrão de propósito |
| 9 | **Nuvem**: Azure + Terraform (exigência da disciplina) | publicado = modo Servidor para a plateia; ESP32 só local (limite da LAN); apresentação em 19/11 |
| 10 | Migrações (Alembic), TLS, login | fora do escopo do protótipo |
| 11 | **Limiares**: ESP32 0,50 (decisão e bomba, do card), `LOW_CONFIDENCE_THRESHOLD` 0,50 (alinhado em 17/11); servidor 0,19 | vêm dos notebooks; recalibrar quando houver fotos reais |
| 12 | Mais de um ESP32 | não suportado nesta versão (um `ESP32_URL`) |
| 13 | Recomendação de chuva: posição real do painel e limiares (1 mm / 10 mm são provisórios) | calibrar observando; testar com a API real |
| 14 | **Modelo grande do servidor** | ResNet50 `resnet50-224-20261116` integrado; pesos na release `modelo-resnet50-20261116` (`scripts/download-model.sh`) |
| 15 | **Faixa de dúvida do servidor** (`SERVER_REVIEW_UNTIL` = 0,50) | provisório; escolher com P(Limpar) foto a foto no conjunto de teste do notebook |
| 16 | **Enquadramento** (`framing.py`) | idêntico ao `preprocess.py` do notebook de tratamento (conferido pixel a pixel); aplicado antes dos dois modelos. Diferença restante: o front reduz a foto a 512 px antes de enviar, o tratamento usou a foto original |
| 17 | Latência do modelo grande no Azure | não medida (≈35–55 ms por foto na CPU do ambiente de teste) |
| 18 | **Rótulos conflitantes no dataset** | o time precisa revisar; afeta a acurácia |