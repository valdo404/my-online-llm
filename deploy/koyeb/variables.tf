# ─── App ──────────────────────────────────────────────────

variable "app_name" {
  type        = string
  description = "Koyeb app name (3-23 chars)"
  default     = "visual-agent"
}

variable "region" {
  type        = string
  description = "Koyeb region (fra=Frankfurt, was=Washington)"
  default     = "fra"
}

# ─── Model ────────────────────────────────────────────────

variable "model_name" {
  type        = string
  description = "HuggingFace model ID"
  default     = "Qwen/Qwen2.5-VL-72B-Instruct"
}

variable "dtype" {
  type        = string
  description = "Data type: bfloat16, float16, auto"
  default     = "bfloat16"
}

variable "max_model_len" {
  type        = number
  description = "Max sequence length (context window)"
  default     = 65536
}

variable "mem_fraction" {
  type        = number
  description = "Fraction of VRAM for KV cache (0.0-1.0)"
  default     = 0.85
}

# ─── GPU / Infra ──────────────────────────────────────────

variable "instance_type" {
  type        = string
  description = "Koyeb GPU instance type slug"
  default     = "gpu-nvidia-4xa100"
}

variable "tensor_parallel" {
  type        = number
  description = "Tensor parallelism (must match GPU count)"
  default     = 4
}

# ─── Scaling ──────────────────────────────────────────────

variable "min_scale" {
  type        = number
  description = "Min instances (0 = scale-to-zero)"
  default     = 0
}

variable "max_scale" {
  type        = number
  description = "Max instances"
  default     = 1
}

# ─── Docker ───────────────────────────────────────────────

variable "docker_image" {
  type        = string
  description = "Docker image (GHCR, Docker Hub, etc.)"
  default     = "ghcr.io/valdo404/my-online-llm:latest"
}

variable "extra_sglang_args" {
  type        = list(string)
  description = "Extra args passed to SGLang launch_server"
  default     = []
}

# ─── Secrets ──────────────────────────────────────────────

variable "hf_token" {
  type        = string
  sensitive   = true
  description = "HuggingFace API token (for gated model access)"
}

variable "api_key" {
  type        = string
  sensitive   = true
  description = "API key to protect the inference endpoint (optional)"
  default     = ""
}

variable "ghcr_username" {
  type        = string
  description = "GitHub Container Registry username"
  default     = ""
}

variable "ghcr_pat" {
  type        = string
  sensitive   = true
  description = "GitHub Container Registry PAT (optional, for private images)"
  default     = ""
}

# ─── Health Check ─────────────────────────────────────────

variable "health_grace_period" {
  type        = number
  description = "Seconds to wait for model to load before health checks (600s for 72B)"
  default     = 600
}
