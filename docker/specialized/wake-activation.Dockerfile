# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/wake-activation

# Install dependencies ONLY (don't install the package itself)
COPY apps/wake-activation/pyproject.toml ./pyproject.toml
RUN apt-get update \
    && apt-get install -y --no-install-recommends libspeexdsp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install --only-binary=:all: "speexdsp-ns==0.1.2" \
    && python -c "import tomllib; data = tomllib.load(open('pyproject.toml','rb')); base_deps = data['project']['dependencies']; opt_deps = data['project'].get('optional-dependencies', {}).get('openwakeword', []); all_deps = base_deps + opt_deps; print('\\n'.join(all_deps))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && python -c "import openwakeword.utils as u; u.download_models(model_names=['__feature_only__'])"

# Source code will be provided via volume mount at /workspace/apps/wake-activation
# This enables live code updates without container rebuild

ENV PYTHONPATH=/workspace/apps/wake-activation

CMD ["python", "-m", "wake_activation"]
