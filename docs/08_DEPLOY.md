# 08 · Execução e implantação

## Modo principal: local, na mesma rede do ESP32
Seu computador roda o backend + PostgreSQL; celular e ESP32 ficam na **mesma rede Wi‑Fi** (a arquitetura da equipe).
```bash
cp .env.example .env            # preencha POSTGRES_PASSWORD, ADMIN_API_KEY, ESP32_URL (IP do Monitor Serial)
docker compose up -d --build    # http://IP-DO-COMPUTADOR:8000  (abra no celular com esse IP)
```
Sem hardware: `docker compose --profile sim up -d --build` e `ESP32_URL=http://simulador:8081`. Sem Docker: `scripts/dev.sh`.
A demonstração funciona **sem internet** (Gemini cai no plano B; a recomendação de chuva mostra "sem dados"). Antes do primeiro `docker compose up`, rode `scripts/download-model.sh` (o build exige o modelo grande; veja `12_MODELO_NO_SERVIDOR.md`).
**Testado em 17/11** com Docker 29: `docker compose --profile sim up -d --build` sobe PostgreSQL + app + simulador (soilnet 2x); análises nos dois
modos gravadas no PostgreSQL e as fotos no volume.

### Armadilhas de rede
- **Isolamento de clientes:** hotspots de celular e Wi‑Fi de visitantes costumam impedir dispositivos de se falarem. Teste `curl http://IP-DO-ESP32/` **do computador** antes. Se falhar, use um roteador seu.
- IP do ESP32 pode mudar (DHCP): reserve o IP no roteador.
- Firewall do computador: libere a porta 8000 para o celular acessar.
- Docker Desktop (Windows/macOS) alcança IPs da LAN normalmente; em Linux também (rede bridge com NAT).

## Nuvem: Terraform na Azure (exigência da disciplina) — leia o limite primeiro
**Um servidor na nuvem não alcança o ESP32 na sua rede local** (IP privado atrás de NAT). Por isso o plano para a apresentação tem dois ambientes:
- **Publicado na Azure:** a plateia abre o link, envia fotos e usa o **modelo grande (modo Servidor)**. O modo ESP32 aparece indisponível (`ESP32_URL` vazio).
- **Local com o ESP32:** `scripts/dev-esp32.sh IP`, para mostrar a placa e o LED/bomba.

O front **não** é separado: o mesmo contêiner serve a API e o front compilado (sem CORS e com um deploy só). Detalhes e comandos: `infra/terraform/README.md`.
Cria: grupo de recursos, registro de imagens (ACR), Container Apps com HTTPS e 1 réplica, e (com `persistent = true`) PostgreSQL gerenciado + Azure Files para as fotos.
O modelo grande vai dentro da imagem (`models/server/` é copiado no `docker build`). Antes do build rode `scripts/download-model.sh`:
o build confere o SHA-256 com `models/server/model.lock` e falha se o modelo faltar ou for outro (`--build-arg ALLOW_NO_MODEL=1` para construir sem ele).

### Limites honestos
- **O que já foi executado (17/11):** build completo das duas imagens; a imagem da app rodando **como na Azure** (sem `DATABASE_URL`, sem ESP32):
  sobe `healthy`, serve o front, o modo Servidor classifica (ResNet50, ~60 ms por foto) e usa **~306 MiB de RAM** (a Azure reserva 2 GiB);
  `terraform init`, `validate` e `fmt -check` (Terraform 1.9.8, azurerm 4.x) passam.
- **O que não foi executado:** `terraform plan`/`apply` (precisam de uma conta Azure) e o envio ao ACR. Espere algum ajuste de região ou cota na
  conta de estudante no primeiro `apply`.
- Contas Azure for Students limitam as regiões e, às vezes, o PostgreSQL: por isso `location` e `persistent` são variáveis.
- Com `persistent = false` (padrão), banco e fotos ficam no disco do contêiner e somem se ele reiniciar.
- O site é público: `ADMIN_API_KEY` é obrigatória; fotos de visitantes ficam no sistema.
- Custo: cobrado enquanto existir; `terraform destroy` depois da apresentação. Segredos ficam no state do Terraform: não versione.