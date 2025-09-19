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
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy voice models from mounted read-only source to writable container location
RUN mkdir -p /voices
COPY main.py .

# At runtime, copy voice models with proper permissions
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /voice-models ]; then cp -r /voice-models/* /voices/ && chmod -R 644 /voices/*; fi && exec python main.py"]
