FROM lmsysorg/sglang:v0.5.6.post2-cu124

LABEL maintainer="valdo404"
LABEL description="SGLang inference server for Qwen2.5-VL-72B-Instruct (4x A100, TP=4)"

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# HuggingFace cache inside the container
ENV HF_HOME=/data/hf-cache
ENV TRANSFORMERS_CACHE=/data/hf-cache
ENV HUGGINGFACE_HUB_CACHE=/data/hf-cache

# SGLang config
ENV SGLANG_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
ENV SGLANG_TP=4
ENV SGLANG_PORT=8000
ENV SGLANG_DTYPE=bfloat16
ENV SGLANG_MEM_FRACTION=0.85
ENV SGLANG_MAX_MODEL_LEN=65536

# Disable CUDA graph for VL models (dynamic input shapes)
ENV SGLANG_DISABLE_CUDA_GRAPH=1

EXPOSE ${SGLANG_PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=600s --retries=5 \
  CMD curl -sf http://localhost:${SGLANG_PORT}/health || exit 1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
