---
name: deploy-terraform
description: Executar localmente com Docker Compose ou implantar na Azure (Container Apps) com Terraform, e explicar os limites de rede com o ESP32. Use ao subir o sistema, publicar ou diagnosticar rede.
---
# Execução e implantação

**Antes de qualquer build:** `scripts/download-model.sh` (modelo grande; o `docker build` falha sem ele, de propósito).

**Principal = local** (computador na mesma rede do ESP32): `cp .env.example .env` → `docker compose up -d --build` (app + PostgreSQL),
ou `--profile sim` (+ simulador com `models/esp32`; `ESP32_URL=http://simulador:8081`). Sem Docker: `scripts/dev.sh`.
Testado em 17/11: build das duas imagens, compose com PostgreSQL + simulador, imagem como na Azure (`healthy`, ~306 MiB de RAM).

**Nuvem (Azure, `infra/terraform/`)**: um contêiner (API + front) no Container Apps + ACR; opcional `persistent = true` (PostgreSQL + Azure Files).
A nuvem **não alcança** o ESP32 da rede local: lá só o modo **Servidor** funciona; o ESP32 se mostra local (`scripts/dev-esp32.sh IP`).
Passo a passo em `infra/terraform/README.md` (apply só do ACR → build/push da imagem → apply do resto). `init`/`validate`/`fmt` passam;
`plan`/`apply` nunca rodaram numa conta real. `terraform.tfvars` e `*.tfstate` têm segredos (ficam fora do git). `terraform destroy` ao fim (custo).
Sem `DATABASE_URL` a imagem usa SQLite em `/data` (some se o contêiner reiniciar).

Rede local — armadilhas: isolamento de clientes em hotspots (teste `curl http://IP-ESP32/` do computador), IP do ESP32 mutável (reserve no roteador), firewall na porta 8000.
