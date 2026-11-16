# Azure: grupo de recursos + registro de imagens (ACR) + Container Apps (a API e o front em UM contêiner).
# Opcional (persistent = true): PostgreSQL gerenciado + Azure Files para as fotos.
# O ESP32 NÃO é alcançável daqui (está na sua rede local): ESP32_URL fica vazio e só o modo "Servidor" funciona.

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

locals {
  base = "${var.name}${random_string.suffix.result}"   # único no mundo (ACR e Storage exigem)
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.name}-${random_string.suffix.result}"
  location = var.location
  tags     = var.tags
}

# ---------------------------------------------------------------- registro de imagens
resource "azurerm_container_registry" "acr" {
  name                = "acr${local.base}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true   # usuário/senha do registro: simples e não exige permissão de papéis (RBAC)
  tags                = var.tags
}

# ---------------------------------------------------------------- logs e ambiente
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${local.base}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5   # trava de custo
  tags                = var.tags
}

resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${local.base}"
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = azurerm_resource_group.rg.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  tags                       = var.tags
}

# ---------------------------------------------------------------- persistência (opcional)
resource "random_password" "db" {
  count   = var.persistent ? 1 : 0
  length  = 24
  special = false
}

resource "azurerm_postgresql_flexible_server" "db" {
  count                         = var.persistent ? 1 : 0
  name                          = "psql-${local.base}"
  resource_group_name           = azurerm_resource_group.rg.name
  location                      = azurerm_resource_group.rg.location
  version                       = "16"
  administrator_login           = "soiling"
  administrator_password        = random_password.db[0].result
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  backup_retention_days         = 7
  public_network_access_enabled = true
  tags                          = var.tags
  lifecycle { ignore_changes = [zone] }
}

resource "azurerm_postgresql_flexible_server_database" "db" {
  count     = var.persistent ? 1 : 0
  name      = "soiling"
  server_id = azurerm_postgresql_flexible_server.db[0].id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# 0.0.0.0 = "permitir serviços do Azure" (o contêiner entra por aqui). Senha forte + SSL obrigatório compensam.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure" {
  count            = var.persistent ? 1 : 0
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.db[0].id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_storage_account" "files" {
  count                    = var.persistent ? 1 : 0
  name                     = "st${local.base}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = var.tags
}

resource "azurerm_storage_share" "images" {
  count              = var.persistent ? 1 : 0
  name               = "images"
  storage_account_id = azurerm_storage_account.files[0].id
  quota              = 5
}

resource "azurerm_container_app_environment_storage" "images" {
  count                        = var.persistent ? 1 : 0
  name                         = "images"
  container_app_environment_id = azurerm_container_app_environment.env.id
  account_name                 = azurerm_storage_account.files[0].name
  share_name                   = azurerm_storage_share.images[0].name
  access_key                   = azurerm_storage_account.files[0].primary_access_key
  access_mode                  = "ReadWrite"
}

locals {
  database_url = var.persistent ? "postgresql+psycopg://soiling:${random_password.db[0].result}@${azurerm_postgresql_flexible_server.db[0].fqdn}:5432/soiling?sslmode=require" : ""
}

# ---------------------------------------------------------------- a aplicação
resource "azurerm_container_app" "app" {
  name                         = "ca-${local.base}"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  revision_mode                = "Single"
  tags                         = var.tags

  registry {
    server               = azurerm_container_registry.acr.login_server
    username             = azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }
  secret {
    name  = "admin-api-key"
    value = var.admin_api_key
  }
  dynamic "secret" {
    for_each = var.persistent ? [1] : []
    content {
      name  = "database-url"
      value = local.database_url
    }
  }
  dynamic "secret" {
    for_each = var.gemini_api_key != "" ? [1] : []
    content {
      name  = "gemini-api-key"
      value = var.gemini_api_key
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = 1   # SQLite e o limite de envios por foto assumem uma instância só

    dynamic "volume" {
      for_each = var.persistent ? [1] : []
      content {
        name         = "images"
        storage_type = "AzureFile"
        storage_name = azurerm_container_app_environment_storage.images[0].name
      }
    }

    container {
      name   = "app"
      image  = "${azurerm_container_registry.acr.login_server}/soiling:${var.image_tag}"
      cpu    = var.cpu
      memory = var.memory

      dynamic "volume_mounts" {
        for_each = var.persistent ? [1] : []
        content {
          name = "images"
          path = "/data/images"
        }
      }

      env {
        name  = "ESP32_URL"
        value = ""   # a nuvem não alcança o ESP32 da sua rede: o modo ESP32 fica indisponível aqui
      }
      env {
        name  = "ESP32_INPUT_SIZE"
        value = tostring(var.esp32_input_size)
      }
      env {
        name  = "ESP32_CLASSES"
        value = var.esp32_classes
      }
      env {
        name  = "SERVER_MODEL_DIR"
        value = "/models/server"
      }
      env {
        name  = "SERVER_INPUT_SIZE"
        value = tostring(var.server_input_size)
      }
      env {
        name        = "ADMIN_API_KEY"
        secret_name = "admin-api-key"
      }
      dynamic "env" {
        for_each = var.persistent ? [1] : []
        content {
          name        = "DATABASE_URL"
          secret_name = "database-url"
        }
      }
      dynamic "env" {
        for_each = var.gemini_api_key != "" ? [1] : []
        content {
          name        = "GEMINI_API_KEY"
          secret_name = "gemini-api-key"
        }
      }
      dynamic "env" {
        for_each = var.gemini_api_key != "" && var.gemini_model != "" ? [1] : []
        content {
          name  = "GEMINI_MODEL"
          value = var.gemini_model
        }
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/api/health"
        port      = 8000
      }
    }
  }
}
