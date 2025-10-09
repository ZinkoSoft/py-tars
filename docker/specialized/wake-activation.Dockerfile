# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/wake-activation

# Install system dependencies including NPU support packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libspeexdsp-dev \
        build-essential \
        python3-dev \
        wget \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies ONLY (don't install the package itself)
COPY apps/wake-activation/pyproject.toml ./pyproject.toml

# Install base dependencies
RUN pip install --upgrade pip \
    && pip install --only-binary=:all: "speexdsp-ns==0.1.2" \
    && python -c "import tomllib; data = tomllib.load(open('pyproject.toml','rb')); base_deps = data['project']['dependencies']; opt_deps = data['project'].get('optional-dependencies', {}).get('openwakeword', []); all_deps = base_deps + opt_deps; print('\\n'.join(all_deps))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Install NPU dependencies (RKNN toolkit - will be skipped gracefully if not on ARM64/RK3588)
RUN pip install --no-deps --ignore-installed rknn-toolkit-lite2==2.3.2 || echo "RKNN Toolkit installation skipped (likely not ARM64/RK3588 platform)"

# Download OpenWakeWord models
RUN python -c "import openwakeword.utils as u; u.download_models(model_names=['__feature_only__'])"

# Source code will be provided via volume mount at /workspace/apps/wake-activation
# This enables live code updates without container rebuild

ENV PYTHONPATH=/workspace/apps/wake-activation

CMD ["python", "-m", "wake_activation"]
