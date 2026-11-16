# Deploy na Azure (Terraform)

Sobe UM contêiner (API + front compilado) no Azure Container Apps, com HTTPS público. O modo **ESP32 não funciona na nuvem**
(o ESP32 está na sua rede local): lá só o modo **Servidor** (modelo grande). O ESP32 você mostra rodando local (`scripts/dev-esp32.sh IP`).

> Escrito sem poder aplicar na Azure: `terraform validate` e o primeiro `apply` são o teste. Mande o erro se aparecer.

## Pré-requisitos
`az` (Azure CLI), `terraform` >= 1.6 e Docker. Entre com `az login` e confirme a assinatura de estudante: `az account show`.

## Passo a passo
```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars      # preencha subscription_id, admin_api_key
terraform init

# 1) cria só o registro de imagens
terraform apply -target=azurerm_resource_group.rg -target=azurerm_container_registry.acr

# 2) constrói e envia a imagem (na RAIZ do projeto; --platform é obrigatório em Mac com chip Apple)
ACR=$(terraform output -raw acr_login_server)
az acr login --name $(terraform output -raw acr_name)
cd ../..
docker build --platform linux/amd64 -t $ACR/soiling:v1 .
docker push $ACR/soiling:v1
cd infra/terraform

# 3) cria o resto
terraform apply
terraform output site_url
```
Nova versão do código: `docker build ... -t $ACR/soiling:v2`, `docker push`, `image_tag = "v2"` no `terraform.tfvars`, `terraform apply`.
Antes do build, copie `model.onnx`, `labels.json` e `model_card.json` para `models/server/` (a imagem leva o modelo dentro).

## Conferir
`curl $(terraform output -raw site_url)/api/health` e abra o `site_url`: o modo Servidor deve aparecer ativo e o modo ESP32 indisponível.
Logs: `az containerapp logs show -n <nome ca-...> -g $(terraform output -raw resource_group) --follow`.

## Variáveis que importam
- `persistent = false` (padrão): SQLite e fotos no disco do contêiner; perdem-se se ele reiniciar. `true`: PostgreSQL + Azure Files.
- `min_replicas = 1`: sempre no ar. Em 0, a primeira visita espera o contêiner subir e carregar o modelo.
- `cpu`/`memory`: o modelo grande roda em CPU; aumente se a inferência ficar lenta.
- `location`: contas Azure for Students limitam as regiões. Se der `RequestDisallowedByAzure` ou "location is restricted", troque e rode de novo.

## Segurança e custo
- O site é público. `admin_api_key` protege correção de rótulo, exclusão e exportação; a análise de foto fica aberta de propósito.
- Fotos enviadas por visitantes ficam no sistema: avise a plateia e não envie imagens pessoais.
- Acompanhe em Cost Management. Para parar o gasto depois da apresentação: `terraform destroy`.
- Nunca versione `terraform.tfvars` nem `*.tfstate` (já estão no `.gitignore`).
