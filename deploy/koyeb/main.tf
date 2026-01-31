terraform {
  required_version = ">= 1.5"

  required_providers {
    koyeb = {
      source  = "koyeb/koyeb"
      version = "~> 0.1"
    }
  }
}

# Auth via KOYEB_TOKEN env var (no HCL attributes)
provider "koyeb" {}

# ─── Secrets ──────────────────────────────────────────────

resource "koyeb_secret" "hf_token" {
  name  = "${var.app_name}-hf-token"
  type  = "SIMPLE"
  value = var.hf_token
}

resource "koyeb_secret" "api_key" {
  count = var.api_key != "" ? 1 : 0
  name  = "${var.app_name}-api-key"
  type  = "SIMPLE"
  value = var.api_key
}

# ─── Registry Secret (GHCR) ──────────────────────────────

resource "koyeb_secret" "ghcr" {
  count = var.ghcr_pat != "" ? 1 : 0
  name  = "${var.app_name}-ghcr"
  type  = "REGISTRY"

  github_registry {
    username = var.ghcr_username
    password = var.ghcr_pat
  }
}

# ─── App ──────────────────────────────────────────────────

resource "koyeb_app" "inference" {
  name = var.app_name
}

# ─── Service: SGLang + Qwen2.5-VL-72B on 4x A100 ────────

resource "koyeb_service" "sglang" {
  app_name = koyeb_app.inference.name

  definition {
    name = "sglang"
    type = "WEB"

    # ── GPU Instance ──
    instance_types {
      type = var.instance_type
    }

    # ── Scale-to-zero ──
    scalings {
      min = var.min_scale
      max = var.max_scale
    }

    regions = [var.region]

    # ── Docker ──
    docker {
      image = var.docker_image

      image_registry_secret = var.ghcr_pat != "" ? koyeb_secret.ghcr[0].name : null

      entrypoint = ["/entrypoint.sh"]

      # Extra args passthrough to entrypoint
      args = var.extra_sglang_args
    }

    # ── Env vars ──
    env {
      key    = "HF_TOKEN"
      secret = koyeb_secret.hf_token.name
    }

    env {
      key   = "SGLANG_MODEL"
      value = var.model_name
    }

    env {
      key   = "SGLANG_TP"
      value = tostring(var.tensor_parallel)
    }

    env {
      key   = "SGLANG_PORT"
      value = "8000"
    }

    env {
      key   = "SGLANG_DTYPE"
      value = var.dtype
    }

    env {
      key   = "SGLANG_MEM_FRACTION"
      value = tostring(var.mem_fraction)
    }

    env {
      key   = "SGLANG_MAX_MODEL_LEN"
      value = tostring(var.max_model_len)
    }

    env {
      key   = "SGLANG_DISABLE_CUDA_GRAPH"
      value = "1"
    }

    dynamic "env" {
      for_each = var.api_key != "" ? [1] : []
      content {
        key    = "SGLANG_API_KEY"
        secret = koyeb_secret.api_key[0].name
      }
    }

    # ── Port / Route ──
    ports {
      port     = 8000
      protocol = "http"
    }

    routes {
      path = "/"
      port = 8000
    }

    # ── Health Check ──
    # Grace period = 600s: le 72B BF16 (~144 GB) met du temps
    # à se télécharger depuis HuggingFace puis à charger en VRAM.
    health_checks {
      grace_period  = var.health_grace_period
      interval      = 30
      timeout       = 10
      restart_limit = 3

      http {
        port = 8000
        path = "/health"
      }
    }
  }

  depends_on = [koyeb_app.inference]
}
