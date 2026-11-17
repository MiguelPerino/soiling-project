variable "subscription_id" {
  type        = string
  description = "ID da assinatura Azure for Students (az account show --query id -o tsv)."
}

variable "location" {
  type        = string
  default     = "brazilsouth"
  description = "Região. Contas Azure for Students só permitem algumas regiões: se der RequestDisallowedByAzure ou 'location is restricted', troque (ex.: eastus2, westus3, canadacentral) e tente de novo."
}

variable "name" {
  type        = string
  default     = "soiling"
  description = "Prefixo dos recursos (minúsculas e números; curto, pois entra em nomes com limite de tamanho)."
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,11}$", var.name))
    error_message = "Use de 2 a 12 caracteres: minúsculas e números, começando por letra."
  }
}

variable "image_tag" {
  type        = string
  default     = "v1"
  description = "Tag da imagem Docker enviada ao registro (muda a cada versão que você publicar)."
}

variable "admin_api_key" {
  type        = string
  sensitive   = true
  description = "ADMIN_API_KEY do backend. Obrigatória: o site é público, e sem ela qualquer pessoa corrige rótulos, apaga análises e exporta fotos."
  validation {
    condition     = length(var.admin_api_key) >= 12
    error_message = "Use pelo menos 12 caracteres."
  }
}

variable "persistent" {
  type        = bool
  default     = false
  description = "false = SQLite e fotos no disco do contêiner (simples; some se o contêiner reiniciar). true = PostgreSQL gerenciado + Azure Files (os dados sobrevivem, custa mais e algumas contas de estudante bloqueiam o PostgreSQL em certas regiões)."
}

variable "min_replicas" {
  type        = number
  default     = 1
  description = "1 = sempre no ar (sem espera na apresentação). 0 = desliga quando ninguém usa (mais barato, mas a primeira visita espera o modelo carregar). Mantenha em 1 com SQLite."
}

variable "cpu" {
  type        = number
  default     = 1.0
  description = "vCPU do contêiner. O modelo grande roda em CPU: se a inferência ficar lenta, aumente (combinações válidas: 1.0/2Gi, 2.0/4Gi)."
}

variable "memory" {
  type        = string
  default     = "2Gi"
  description = "Memória do contêiner."
}

variable "esp32_classes" {
  type    = string
  default = "LIMPO,SEVERO"
}

variable "esp32_input_size" {
  type    = number
  default = 112
}

variable "server_input_size" {
  type        = number
  default     = 0
  description = "0 = usa o input_size do model_card.json do modelo grande."
}

variable "server_review_until" {
  type        = number
  default     = 0.5
  description = "Topo da faixa de dúvida do modelo grande (PROVISÓRIO): limiar do card <= P(precisa limpar) < isto => revisão humana."
}

variable "gemini_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "gemini_model" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = { projeto = "soiling-detection" }
}
