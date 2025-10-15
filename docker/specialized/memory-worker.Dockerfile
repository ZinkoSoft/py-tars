FROM python:3.11-slim

WORKDIR /app

# Build arg to enable NPU model conversion at build time
ARG NPU_EMBEDDER_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install tars-core first (cached unless tars-core changes)
COPY packages/tars-core/pyproject.toml packages/tars-core/README.md /tmp/tars-core/
COPY packages/tars-core/src /tmp/tars-core/src
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install memory-worker dependencies ONLY (cached unless pyproject.toml changes)
COPY apps/memory-worker/pyproject.toml /tmp/memory-worker/pyproject.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/memory-worker/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -rf /tmp/memory-worker /tmp/requirements.txt

# Conditionally install RKNN toolkit dependencies (always install if NPU enabled)
# This allows runtime model conversion without rebuilding the image
RUN if [ "$NPU_EMBEDDER_ENABLED" = "1" ]; then \
        echo "Installing RKNN toolkit and dependencies for NPU support..." && \
        # Install onnx and onnxruntime first
        pip install --no-cache-dir onnx onnxruntime && \
        # Install onnxoptimizer (needs cmake)
        pip install --no-cache-dir onnxoptimizer==0.3.8 && \
        # Install rknn-toolkit2 (for model conversion)
        pip install --no-cache-dir rknn-toolkit2 && \
        # Install rknn-toolkit-lite2 (for runtime inference)
        pip install --no-cache-dir rknn-toolkit-lite2 && \
        echo "RKNN toolkit installed successfully"; \
    else \
        echo "NPU embedder disabled - skipping RKNN toolkit"; \
    fi

# Copy conversion scripts (needed for runtime NPU model preparation)
COPY apps/memory-worker/scripts /app/scripts
RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

# Copy startup script that checks/converts models at runtime
COPY docker/specialized/memory-worker-entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Source code will be provided via volume mount at /workspace/apps/memory-worker
# This enables live code updates without container rebuild
# Note: memory-worker now uses src/ layout, so PYTHONPATH includes src/ directory

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace/apps/memory-worker/src:/workspace/packages/tars-core/src:/app \
    HF_HOME=/data/model_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/model_cache \
    TRANSFORMERS_CACHE=/data/model_cache \
    TORCH_HOME=/data/model_cache

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "memory_worker"]
