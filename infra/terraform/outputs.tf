output "site_url" {
  value       = "https://${azurerm_container_app.app.ingress[0].fqdn}"
  description = "Endereço público do sistema (front + API)."
}

output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "resource_group" {
  value = azurerm_resource_group.rg.name
}
