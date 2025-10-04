FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
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

# Source code will be provided via volume mount at /workspace/apps/memory-worker
# This enables live code updates without container rebuild

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/data/model_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/model_cache \
    TRANSFORMERS_CACHE=/data/model_cache \
    TORCH_HOME=/data/model_cache

CMD ["python", "-m", "memory_worker"]
