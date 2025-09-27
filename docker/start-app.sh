#!/bin/sh
# Generic launcher for app containers built from docker/app.Dockerfile.
# Precedence order:
#   1. If the container was started with an explicit command/args, run them.
#   2. Else if APP_CMD is non-empty, execute it via the shell (allows pipelines).
#   3. Else if APP_MODULE is non-empty, run it with `python -m`.
#   4. Otherwise, keep the container alive without launching an app (sleep).

set -e

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ -n "${APP_CMD}" ]; then
  exec sh -lc "${APP_CMD}"
fi

if [ -n "${APP_MODULE}" ]; then
  exec python -m "${APP_MODULE}"
fi

echo "No APP_CMD or APP_MODULE provided; container will idle." >&2
exec tail -f /dev/null
