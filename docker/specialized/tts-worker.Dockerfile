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
COPY apps/tts-worker/README.md /tmp/tts-worker/README.md
# Create empty package structure for pip install to work (tts_worker + external_services)
RUN mkdir -p /tmp/tts-worker/tts_worker /tmp/tts-worker/external_services && \
    touch /tmp/tts-worker/tts_worker/__init__.py && \
    touch /tmp/tts-worker/external_services/__init__.py
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir /tmp/tts-worker && rm -rf /tmp/tts-worker

# Copy source code LAST (this layer invalidates most frequently)
COPY apps/tts-worker/tts_worker /app/tts_worker
COPY apps/tts-worker/external_services /app/external_services

# Copy voice models from mounted read-only source to writable container location
RUN mkdir -p /voices

# At runtime, copy voice models with proper permissions
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /voice-models ] && [ \"$(ls -A /voice-models 2>/dev/null)\" ]; then cp -r /voice-models/* /voices/ && chmod -R 644 /voices/*; else echo 'No voice models mounted at /voice-models'; fi; if [ ! -f /voices/TARS.onnx ]; then echo 'WARNING: /voices/TARS.onnx not found'; fi; exec python -m tts_worker"]
