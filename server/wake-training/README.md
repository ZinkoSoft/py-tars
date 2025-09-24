# Wake Training Service Container

This folder holds the Docker assets and FastAPI control plane for the wake-word training stack that will run on the Jetson Orin Nano (or any other CUDA-capable host). The current build ships dataset management endpoints; subsequent sprints will add recording ingestion, GPU training jobs, and deployment tooling.

## Contents

- `Dockerfile` – base image + system deps. Override `BASE_IMAGE` during build if you want an NVIDIA L4T image instead of the default Python slim image.
- `requirements.txt` – Python dependencies for the control plane (FastAPI, uvicorn, Pydantic, etc.).
- `docker-compose.yml` – single-service compose file that exposes port `8080` and mounts the host training data directory with read/write permissions.
- `wake_training/` – FastAPI application package.

## Host data directory

The compose file mounts `${WAKE_TRAINING_HOST_DATA_DIR:-../../data/wake-training}` into the container at `/data/wake-training` with `:rw` permissions. This ensures the Jetson can persist datasets, training artifacts, and deployment bundles in a location the host (and CI) can inspect.

The repository now includes a matching `data/wake-training/` directory (with a `.gitkeep` placeholder). If you want to use a different path on the Jetson, export `WAKE_TRAINING_HOST_DATA_DIR=/absolute/host/path` before running compose.

## Usage

```bash
cd server/wake-training
# Optional: override defaults for Jetson builds
export WAKE_TRAINING_BASE_IMAGE=nvcr.io/nvidia/l4t-ml:r36.2.0-py3
export WAKE_TRAINING_HOST_DATA_DIR=/opt/wake-training-data
mkdir -p "$WAKE_TRAINING_HOST_DATA_DIR"

# Build and start the container (runs uvicorn on port 8080)
docker compose up --build -d
```

### Cross-origin access

When serving the Vue console from a different host, configure the allowed origins via `WAKE_TRAINING_CORS_ORIGINS` (comma separated). The default allows `http://localhost:5173` and `http://127.0.0.1:5173` for local development.

```bash
export WAKE_TRAINING_CORS_ORIGINS=http://localhost:5173,http://192.168.7.1:4173
```

### API endpoints (current MVP)

- `GET /health` – basic status + resolved data root path.
- `GET /datasets` – list datasets with clip counts and creation time.
- `POST /datasets` – create a new dataset directory. Existing names return HTTP 409.
- `GET /datasets/{name}` – fetch dataset details (including soft-deleted clip count).

File operations occur under the mounted `/data/wake-training` directory. Future milestones will add recording ingestion, training jobs, and deployment actions.

## Next steps

1. Add recording ingestion endpoints and background metrics collection.
2. Extend the compose file with additional services (e.g., Redis) as outlined in `plan/wake_training_plan.md`.
3. Create an `.env` file in this directory for secrets (Orange Pi SSH creds, dataset tokens) before deploying to real hardware.
4. Implement the GPU training worker container and job orchestration path.
