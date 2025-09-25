# Wake Training UI (Vue)

Single-page Vue app for curating wake-word datasets, monitoring training jobs, and tailing log streams. It targets the wake-training FastAPI backend over REST + WebSockets.

### Key capabilities

- Visual dataset summaries, rename/delete, and trash management
- Inline recorder for collecting fresh clips from the browser
- Live job cards with log streaming over WebSockets
- **Decision-threshold tuning** directly on each dataset card; the chosen value is sent as a config override when you queue the next training job, and the UI updates when completed jobs report their effective threshold

## Quick start (Docker Compose)

Run the UI directly in Docker without installing Node:

```bash
API_HOST=jetson-host API_PORT=8000 docker compose up --build
```

The compose file mounts the source tree, installs dependencies, and runs `npm run dev` inside the container. The Vue dev server binds to the internal port `5173`; the companion HTTPS proxy (described below) terminates TLS and forwards `/api` + `/ws` calls to the backend defined by `API_HOST` / `API_PORT`.

## Local Node workflow

Prefer a local toolchain? Install dependencies and start Vite yourself:

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Set the backend origin in `.env.local` or your shell:

```
VITE_API_BASE_URL=http://jetson-host:8000
```

To inspect a production-style bundle:

```bash
npm run build
npm run preview
```

## Production image

A multi-stage Dockerfile is provided for hardened builds:

```bash
docker build -t wake-training-ui .
docker run --rm -p 4173:4173 wake-training-ui
```

The container runs `npm run preview` and exposes port `4173` by default.

## HTTPS via self-signed proxy

Browsers only unlock `getUserMedia` on secure origins. The supplied `docker-compose.yml` includes a `wake-training-proxy` service based on nginx that generates a self-signed certificate and forwards HTTPS traffic to the Vite dev server.

Launch both services with subject-alternative-names that match your Jetson IP. The proxy can also forward API/WebSocket traffic to the backend so the UI talks to the server through the same HTTPS origin:

```bash
HTTPS_PORT=5173 \
TLS_SAN="DNS:localhost,IP:192.168.7.134" \
API_HOST=192.168.7.134 \
API_PORT=8080 \
docker compose up --build
```

Key details:

- `HTTPS_PORT` controls the host port that nginx listens on (defaults to `5173`).
- `TLS_SAN` must list every hostname or IP you will hit in the browser. Add `IP:your.jetson.ip` so Chrome/Firefox grant mic access.
- `API_HOST` / `API_PORT` point at the wake-training FastAPI instance; tweak `API_SCHEME=https` if the API already uses TLS.
- Certificates live in the named `certs` volume. Delete the volume to regenerate.

Trust the generated certificate once (e.g. Keychain Access on macOS, `certmgr.msc` on Windows, or `update-ca-trust` on Linux). Afterwards, load `https://<host>:<HTTPS_PORT>`, allow microphone permissions, and the proxy will relay traffic (including `/api/*` and `/ws/*`) to the backend while serving the Vue dev server.
