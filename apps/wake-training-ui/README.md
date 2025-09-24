# Wake Training UI (Vue)

Single-page Vue application for managing datasets, jobs, and logs in the wake-word training workflow. The UI
consumes the FastAPI service exposed under `server/wake-training` and listens to WebSocket events for live
updates.

## Getting started

# Wake Training UI (Vue)

Single-page Vue application for managing datasets, jobs, and logs in the wake-word training workflow. The UI consumes the FastAPI service exposed under `server/wake-training` and listens to WebSocket events for live updates.

## Getting started (Docker-first)

Launch the dev server without installing Node locally:

```bash
npm run preview
```

The container mounts the project directory and runs Vite on <http://localhost:5173>. To target a remote Jetson API, export the base URL before launching:

```bash
export VITE_API_BASE_URL=http://jetson-host:8000
```
```

### Production image

Build and serve the production bundle entirely in Docker:

```bash

A development-friendly multi-stage Dockerfile is provided. To build and serve the production bundle:
```

The preview container exposes port `4173`.

## Local Node workflow (optional)

If you prefer a local toolchain:

```bash
npm install
npm run dev
```

Configure the backend origin via `.env.local`:

```
VITE_API_BASE_URL=http://jetson-host:8000
```

To inspect a production build locally:

```bash
npm run build
npm run preview
```

```bash
docker build -t wake-training-ui .
docker run --rm -p 4173:4173 wake-training-ui
```

The container runs `npm run preview` on port `4173` by default.
