# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# Default to aarch64 (Raspberry Pi 5 64-bit Ubuntu). Override with --build-arg PIPER_ARCH=linux_x86_64 when building on x86_64.
ARG PIPER_ARCH=linux_aarch64
ARG PIPER_VERSION=2023.11.14-2
ENV PYTHONUNBUFFERED=1 PIPER_VERSION=${PIPER_VERSION} PIPER_ARCH=${PIPER_ARCH}

# Install system dependencies (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils sox psmisc ca-certificates pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies with cache mount (BuildKit feature)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip

# Install tars-core (cached unless tars-core changes)
COPY packages/tars-core/pyproject.toml packages/tars-core/README.md /tmp/tars-core/
COPY packages/tars-core/src /tmp/tars-core/src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir /tmp/tars-core && rm -rf /tmp/tars-core

# Install Piper TTS (cached layer)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install piper-tts

# Install TTS worker dependencies ONLY (cached unless pyproject.toml changes)
COPY apps/tts-worker/pyproject.toml /tmp/tts-worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/tts-worker/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -rf /tmp/tts-worker /tmp/requirements.txt

# Source code will be provided via volume mount at /workspace/apps/tts-worker
# This enables live code updates without container rebuild

# Copy voice models from mounted read-only source to writable container location
RUN mkdir -p /voices

# Set PYTHONPATH to workspace mount (will be overridden by compose.yml)
ENV PYTHONPATH=/app

# At runtime, copy voice models with proper permissions
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /voice-models ] && [ \"$(ls -A /voice-models 2>/dev/null)\" ]; then cp -r /voice-models/* /voices/ && chmod -R 644 /voices/*; else echo 'No voice models mounted at /voice-models'; fi; if [ ! -f /voices/TARS.onnx ]; then echo 'WARNING: /voices/TARS.onnx not found'; fi; exec python -m tts_worker"]
