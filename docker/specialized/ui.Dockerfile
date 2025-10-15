FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev \
    libasound2 \
    libdrm2 libgbm1 libegl1 libgles2 libgl1 libglx0 libglx-mesa0 libglu1-mesa \
    libx11-6 libx11-xcb1 libxext6 libxrender1 libxrandr2 libxcursor1 libxi6 \
    libxfixes3 libxdamage1 libxxf86vm1 libxshmfence1 \
    # ---- add these XCB pieces (important) ----
    libxcb1 libxcb-dri2-0 libxcb-dri3-0 libxcb-present0 libxcb-shm0 \
    libxcb-sync1 libxcb-randr0 libxcb-xfixes0 libxcb-glx0 \
    # ------------------------------------------
    mesa-utils mesa-utils-extra glmark2-es2 kmscube \
    fontconfig fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy tars-core package first (needed for contracts)
COPY packages/tars-core /tmp/tars-core

# Copy pyproject.toml for dependency installation
COPY apps/ui/pyproject.toml ./pyproject.toml
COPY apps/ui/src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    pip install --no-cache-dir -e .

# Copy configuration files (layout.json, ui.toml) - stay at root
COPY apps/ui/layout.json ./layout.json
COPY apps/ui/ui.toml ./ui.toml

ENV UI_CONFIG="/config/ui.toml"

CMD ["python", "-m", "ui"]
