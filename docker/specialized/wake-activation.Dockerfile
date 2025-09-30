# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/wake-activation

COPY apps/wake-activation/pyproject.toml ./
COPY apps/wake-activation/wake_activation ./wake_activation
COPY models/openwakeword /models/openwakeword
RUN apt-get update \
    && apt-get install -y --no-install-recommends libspeexdsp-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install --only-binary=:all: "speexdsp-ns==0.1.2" \
    && pip install -e ".[openwakeword]" \
    && python -c "import openwakeword.utils as u; u.download_models(model_names=['__feature_only__'])"

CMD ["python", "-m", "wake_activation"]
