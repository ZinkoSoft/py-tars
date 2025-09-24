#!/bin/sh
set -euo pipefail

CERT_DIR=${CERT_DIR:-/etc/nginx/certs}
CERT_PATH=${TLS_CERT_PATH:-${CERT_DIR}/selfsigned.crt}
KEY_PATH=${TLS_KEY_PATH:-${CERT_DIR}/selfsigned.key}
KEY_BITS=${TLS_KEY_BITS:-2048}
DAYS=${TLS_DAYS:-365}
SUBJECT=${TLS_SUBJECT:-/CN=localhost}
SAN=${TLS_SAN:-DNS:localhost,IP:127.0.0.1}
UPSTREAM_HOST=${UPSTREAM_HOST:-wake-training-ui}
UPSTREAM_PORT=${UPSTREAM_PORT:-5173}

echo "[proxy] ensuring certificates exist in ${CERT_DIR}" >&2
mkdir -p "${CERT_DIR}"
if [ ! -f "${CERT_PATH}" ] || [ ! -f "${KEY_PATH}" ]; then
  echo "[proxy] generating self-signed certificate" >&2
  openssl req -x509 -nodes -days "${DAYS}" -newkey rsa:"${KEY_BITS}" \
    -keyout "${KEY_PATH}" \
    -out "${CERT_PATH}" \
    -subj "${SUBJECT}" \
    -addext "subjectAltName=${SAN}" >&2
else
  echo "[proxy] reusing existing certificate" >&2
fi

export TLS_CERT_PATH CERT_PATH TLS_KEY_PATH KEY_PATH UPSTREAM_HOST UPSTREAM_PORT

echo "[proxy] rendering nginx configuration" >&2
envsubst '${TLS_CERT_PATH} ${TLS_KEY_PATH} ${UPSTREAM_HOST} ${UPSTREAM_PORT} ${API_SCHEME} ${API_HOST} ${API_PORT}' \
  < /etc/nginx/templates/nginx.conf.template \
  > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
