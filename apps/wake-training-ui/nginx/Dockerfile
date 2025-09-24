FROM mirror.gcr.io/library/nginx:1.27-alpine

RUN apk add --no-cache openssl gettext

ENV CERT_DIR=/etc/nginx/certs \
    TLS_CERT_PATH=/etc/nginx/certs/selfsigned.crt \
    TLS_KEY_PATH=/etc/nginx/certs/selfsigned.key \
    TLS_KEY_BITS=2048 \
    TLS_DAYS=365 \
    TLS_SUBJECT=/CN=localhost \
    TLS_SAN=DNS:localhost,IP:127.0.0.1 \
    UPSTREAM_HOST=wake-training-ui \
    UPSTREAM_PORT=5173 \
    API_SCHEME=http \
    API_HOST=127.0.0.1 \
    API_PORT=8000

COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 443

ENTRYPOINT ["/entrypoint.sh"]
