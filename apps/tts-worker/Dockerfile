FROM python:3.11-slim

# Default to aarch64 (Raspberry Pi 5 64-bit Ubuntu). Override with --build-arg PIPER_ARCH=linux_x86_64 when building on x86_64.
ARG PIPER_ARCH=linux_aarch64
ARG PIPER_VERSION=2023.11.14-2
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIPER_VERSION=${PIPER_VERSION} PIPER_ARCH=${PIPER_ARCH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils sox psmisc ca-certificates pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Piper via pip (includes all dependencies) instead of GitHub binary
RUN pip install --upgrade pip && pip install piper-tts

WORKDIR /app
COPY packages/tars-core /tmp/tars-core
RUN pip install --no-cache-dir /tmp/tars-core && rm -rf /tmp/tars-core

# Install worker via wheel to align with centralized build pipeline
COPY apps/tts-worker/pyproject.toml /tmp/tts-worker/pyproject.toml
COPY apps/tts-worker/README.md /tmp/tts-worker/README.md
COPY apps/tts-worker/tts_worker /tmp/tts-worker/tts_worker
COPY apps/tts-worker/external_services /tmp/tts-worker/external_services
RUN pip install --no-cache-dir /tmp/tts-worker && \
    rm -rf /tmp/tts-worker

# Copy voice models from mounted read-only source to writable container location
RUN mkdir -p /voices

# At runtime, copy voice models with proper permissions
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /voice-models ] && [ \"$(ls -A /voice-models 2>/dev/null)\" ]; then cp -r /voice-models/* /voices/ && chmod -R 644 /voices/*; else echo 'No voice models mounted at /voice-models'; fi; if [ ! -f /voices/TARS.onnx ]; then echo 'WARNING: /voices/TARS.onnx not found'; fi; exec python -m tts_worker"]
