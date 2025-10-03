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
COPY apps/memory-worker/README.md /tmp/memory-worker/README.md
# Create empty package structure for pip install to work
RUN mkdir -p /tmp/memory-worker/memory_worker && \
    touch /tmp/memory-worker/memory_worker/__init__.py
RUN pip install --no-cache-dir /tmp/memory-worker && \
    rm -rf /tmp/memory-worker

# Copy source code LAST (this layer invalidates when source changes)
COPY apps/memory-worker/memory_worker /app/memory_worker

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/data/model_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/model_cache \
    TRANSFORMERS_CACHE=/data/model_cache \
    TORCH_HOME=/data/model_cache

CMD ["python", "-m", "memory_worker"]
