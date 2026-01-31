#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ─── Couleurs ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── Pré-requis ──────────────────────────────────────────

check_prereqs() {
    local missing=0

    if ! command -v terraform &>/dev/null; then
        error "terraform not found. Install: https://developer.hashicorp.com/terraform/install"
        missing=1
    fi

    if ! command -v docker &>/dev/null; then
        error "docker not found. Install: https://docs.docker.com/get-docker/"
        missing=1
    fi

    if ! command -v koyeb &>/dev/null; then
        warn "koyeb CLI not found. Install: https://www.koyeb.com/docs/build-and-deploy/cli/installation"
        warn "Le CLI est optionnel mais utile pour le debug."
    fi

    if [ -z "${KOYEB_TOKEN:-}" ]; then
        error "KOYEB_TOKEN is not set. Export it:"
        error "  export KOYEB_TOKEN=your-koyeb-api-token"
        missing=1
    fi

    if [ ! -f terraform.tfvars ]; then
        if [ -f terraform.tfvars.example ]; then
            error "terraform.tfvars not found. Create it:"
            error "  cp terraform.tfvars.example terraform.tfvars"
            error "  # then fill in hf_token"
        else
            error "terraform.tfvars not found."
        fi
        missing=1
    fi

    if [ "$missing" -eq 1 ]; then
        exit 1
    fi
}

# ─── Build & Push Docker image ────────────────────────────

build_and_push() {
    local image="${1:-ghcr.io/valdo404/my-online-llm:latest}"

    info "Building Docker image: $image"
    docker build -t "$image" .

    info "Pushing Docker image: $image"
    docker push "$image"

    info "Docker image pushed successfully."
}

# ─── Discover GPU instance types ──────────────────────────

discover_gpus() {
    info "Querying Koyeb GPU catalog..."
    curl -sf -H "Authorization: Bearer ${KOYEB_TOKEN}" \
        https://app.koyeb.com/v1/catalog/instance_types \
        | python3 -c "
import sys, json
data = json.load(sys.stdin)
types = data.get('instance_types', data) if isinstance(data, dict) else data
for t in types:
    name = t.get('id', t.get('name', '?'))
    gpu = t.get('gpu', {})
    if gpu:
        brand = gpu.get('brand', '')
        model = gpu.get('model', '')
        count = gpu.get('count', 1)
        vram  = gpu.get('memory', '?')
        price = t.get('price_per_second', {}).get('amount', '?')
        print(f'  {name:40s}  {count}x {brand} {model}  VRAM={vram}  price/s={price}')
" 2>/dev/null || warn "Could not parse GPU catalog. Raw output:"
}

# ─── Terraform ────────────────────────────────────────────

tf_init() {
    info "Terraform init..."
    terraform init -upgrade
}

tf_plan() {
    info "Terraform plan..."
    terraform plan -out=tfplan
}

tf_apply() {
    info "Terraform apply..."
    terraform apply tfplan
    rm -f tfplan

    echo ""
    info "=== Deployment complete ==="
    terraform output
}

# ─── Main ─────────────────────────────────────────────────

usage() {
    cat <<EOF
Usage: $0 <command>

Commands:
  check       Check prerequisites
  gpus        List available GPU instance types on Koyeb
  build       Build and push Docker image
  init        Terraform init
  plan        Terraform plan
  apply       Terraform apply (deploy)
  deploy      Full pipeline: check + init + plan + apply
  output      Show Terraform outputs
  status      Show service status via Koyeb API
  wake        Send a request to wake the service from scale-to-zero
  destroy     Terraform destroy (remove everything)

Environment:
  KOYEB_TOKEN    Koyeb API token (required)
  DOCKER_IMAGE   Override Docker image (default: from terraform.tfvars)

EOF
}

case "${1:-}" in
    check)
        check_prereqs
        info "All prerequisites OK."
        ;;
    gpus)
        discover_gpus
        ;;
    build)
        check_prereqs
        build_and_push "${DOCKER_IMAGE:-ghcr.io/valdo404/my-online-llm:latest}"
        ;;
    init)
        check_prereqs
        tf_init
        ;;
    plan)
        check_prereqs
        tf_init
        tf_plan
        ;;
    apply)
        tf_apply
        ;;
    deploy)
        check_prereqs
        tf_init
        tf_plan
        tf_apply
        ;;
    output)
        terraform output
        ;;
    status)
        info "Querying service status..."
        APP_NAME=$(terraform output -raw app_id 2>/dev/null || echo "")
        if [ -n "$APP_NAME" ]; then
            curl -sf -H "Authorization: Bearer ${KOYEB_TOKEN}" \
                "https://app.koyeb.com/v1/apps/${APP_NAME}" | python3 -m json.tool
        else
            warn "No app deployed. Run: $0 deploy"
        fi
        ;;
    wake)
        URL=$(terraform output -raw health_endpoint 2>/dev/null || echo "")
        if [ -n "$URL" ]; then
            info "Waking service: $URL"
            curl -sf -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" "$URL" || true
            info "Service is waking up. The first request after scale-to-zero takes 3-10 min."
        else
            warn "No service URL. Run: $0 deploy"
        fi
        ;;
    destroy)
        warn "This will DESTROY all Koyeb resources."
        read -rp "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            terraform destroy -auto-approve
            info "All resources destroyed."
        else
            info "Cancelled."
        fi
        ;;
    *)
        usage
        ;;
esac
