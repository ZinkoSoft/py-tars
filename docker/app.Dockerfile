# docker/app.Dockerfile
#
# Reusable multi-stage Dockerfile for ANY app in the monorepo.
# Build args (set per-service in compose):
#   - PY_VERSION   : Python version (default 3.11)
#   - APP_PATH     : Path to the app (e.g., apps/router)
#   - CONTRACTS_PATH: Path to contracts package (default packages/tars-core)
#   - APP_MODULE   : Python module to run with `python -m` (e.g., tars_router.app_main)
#   - APP_CMD      : Optional shell command to run instead of APP_MODULE (e.g., "uvicorn server:app --host 0.0.0.0 --port 5010")
#
# Compose can override the final `command:` to use a console_script instead.

ARG PY_VERSION=3.11

FROM python:${PY_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
  && rm -rf /var/lib/apt/lists/*
RUN useradd -m app
WORKDIR /app

# ---------- Builder: build wheels for contracts + selected app ----------
FROM base AS builder
ARG APP_PATH
ARG CONTRACTS_PATH=packages/tars-core
RUN python -m pip install --upgrade pip build wheel
# Copy only metadata first to leverage Docker layer cache
COPY ${CONTRACTS_PATH}/pyproject.toml /src/contracts/pyproject.toml
COPY ${APP_PATH}/pyproject.toml        /src/app/pyproject.toml
# Now copy sources
COPY ${CONTRACTS_PATH} /src/contracts
COPY ${APP_PATH} /src/app
# Build wheels
RUN python -m build /src/contracts
RUN python -m build /src/app

# ---------- Runtime: install wheels and run ----------
FROM base AS runtime
ARG APP_MODULE=tars_router.app_main
ARG APP_CMD=""
ENV APP_MODULE=${APP_MODULE}
ENV APP_CMD=${APP_CMD}
COPY --from=builder /src/contracts/dist/*.whl /wheels/
COPY --from=builder /src/app/dist/*.whl /wheels/
RUN pip install --no-cache-dir /wheels/*.whl
COPY docker/start-app.sh /usr/local/bin/start-app
RUN chmod +x /usr/local/bin/start-app
USER app
ENTRYPOINT ["/usr/bin/tini","--","/usr/local/bin/start-app"]
# Compose can override command. start-app respects explicit commands, APP_CMD, or APP_MODULE (in that order).
# If neither is provided, the container idles (tail -f /dev/null) so services like the web UI can defer startup.
CMD []
