output "app_id" {
  value       = koyeb_app.inference.id
  description = "Koyeb App ID"
}

output "service_id" {
  value       = koyeb_service.sglang.id
  description = "Koyeb Service ID"
}

output "service_url" {
  value       = "https://${var.app_name}.koyeb.app"
  description = "Public URL of the inference endpoint"
}

output "api_endpoint" {
  value       = "https://${var.app_name}.koyeb.app/v1/chat/completions"
  description = "OpenAI-compatible chat completions endpoint"
}

output "health_endpoint" {
  value       = "https://${var.app_name}.koyeb.app/health"
  description = "Health check URL"
}

output "models_endpoint" {
  value       = "https://${var.app_name}.koyeb.app/v1/models"
  description = "List available models"
}

output "config_summary" {
  value = {
    model         = var.model_name
    instance_type = var.instance_type
    tp            = var.tensor_parallel
    dtype         = var.dtype
    region        = var.region
    scale_to_zero = var.min_scale == 0
    cost_per_hour = "$6.40/h (4x A100 PCIe)"
  }
  description = "Deployment configuration summary"
}
