#!/bin/bash
set -euo pipefail

echo "============================================"
echo " SGLang Inference Server"
echo " Model:  ${SGLANG_MODEL}"
echo " TP:     ${SGLANG_TP}"
echo " Dtype:  ${SGLANG_DTYPE}"
echo " Port:   ${SGLANG_PORT}"
echo " Mem:    ${SGLANG_MEM_FRACTION}"
echo " MaxLen: ${SGLANG_MAX_MODEL_LEN}"
echo "============================================"

# Ensure cache directory exists
mkdir -p "${HF_HOME}"

# Show GPU info
echo ""
echo "--- GPU Info ---"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || echo "nvidia-smi not available"
echo ""

# Build args
ARGS=(
    --model-path "${SGLANG_MODEL}"
    --host 0.0.0.0
    --port "${SGLANG_PORT}"
    --tp "${SGLANG_TP}"
    --dtype "${SGLANG_DTYPE}"
    --mem-fraction-static "${SGLANG_MEM_FRACTION}"
    --max-model-len "${SGLANG_MAX_MODEL_LEN}"
    --tool-call-parser qwen25
    --trust-remote-code
)

# Disable CUDA graph for VL models (dynamic image sizes)
if [ "${SGLANG_DISABLE_CUDA_GRAPH:-1}" = "1" ]; then
    ARGS+=(--disable-cuda-graph)
    echo "CUDA graph disabled (VL model)"
fi

# Optional: API key protection
if [ -n "${SGLANG_API_KEY:-}" ]; then
    ARGS+=(--api-key "${SGLANG_API_KEY}")
    echo "API key protection enabled"
fi

# Extra args passthrough (from docker CMD / koyeb args)
if [ $# -gt 0 ]; then
    ARGS+=("$@")
fi

echo ""
echo "Launching: python3 -m sglang.launch_server ${ARGS[*]}"
echo ""

exec python3 -m sglang.launch_server "${ARGS[@]}"
