# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# Install system dependencies for audio and Faster-Whisper (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils \
    pulseaudio-utils \
    libasound2-plugins \
    portaudio19-dev \
    python3-dev \
    gcc \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set Hugging Face cache environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/models
ENV HUGGINGFACE_HUB_CACHE=/app/models
ENV TRANSFORMERS_CACHE=/app/models

# Install tars-core first (cached unless tars-core changes)
COPY packages/tars-core/pyproject.toml packages/tars-core/README.md /tmp/tars-core/
COPY packages/tars-core/src /tmp/tars-core/src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install STT worker dependencies ONLY (cached unless requirements.txt or pyproject.toml changes)
COPY apps/stt-worker/requirements.txt /app/requirements.txt
COPY apps/stt-worker/pyproject.toml /tmp/stt-worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/requirements.txt && \
    python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/stt-worker/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/stt-requirements.txt && \
    pip install -r /tmp/stt-requirements.txt && \
    rm -rf /tmp/stt-worker /tmp/stt-requirements.txt

# Source code will be provided via volume mount at /workspace/apps/stt-worker
# This enables live code updates without container rebuild
# With src/ layout, code is at /workspace/apps/stt-worker/src/stt_worker

# Create directories for models
RUN mkdir -p /app/models /host-models

# Set PYTHONPATH to workspace mount to find src/ layout
# Format: /workspace/apps/stt-worker/src
ENV PYTHONPATH=/workspace/apps/stt-worker/src

# Use entrypoint to copy models from host mount if available
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /host-models ] && [ -n \"$(ls -A /host-models 2>/dev/null)\" ]; then echo 'Copying models from host...'; cp -r /host-models/* /app/models/ 2>/dev/null || true; fi; exec python -m stt_worker"]
