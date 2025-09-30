FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/tars-core /tmp/tars-core
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install worker as a wheel so the image mirrors the centralized build process
COPY apps/memory-worker/pyproject.toml /tmp/memory-worker/pyproject.toml
COPY apps/memory-worker/README.md /tmp/memory-worker/README.md
COPY apps/memory-worker/memory_worker /tmp/memory-worker/memory_worker
RUN pip install --no-cache-dir /tmp/memory-worker && \
    rm -rf /tmp/memory-worker

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/data/model_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/model_cache \
    TRANSFORMERS_CACHE=/data/model_cache \
    TORCH_HOME=/data/model_cache

CMD ["python", "-m", "memory_worker"]
