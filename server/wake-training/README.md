# Wake Training Service Container

This folder holds the Docker assets and FastAPI control plane for the wake-word training stack that will run on the Jetson Orin Nano (or any other CUDA-capable host). The service now supports dataset management, recording ingestion, an in-process PyTorch training pipeline, and artifact export for wake models.

## Contents

- `Dockerfile` – base image + system deps. Override `BASE_IMAGE` during build if you want an NVIDIA L4T image instead of the default Python slim image.
- `requirements.txt` – Python dependencies (FastAPI, PyTorch, SciPy, SoundFile, etc.).
- `docker-compose.yml` – single-service compose file that exposes port `8080` and mounts the host training data directory with read/write permissions.
- `wake_training/` – FastAPI application package, including the training pipeline in `trainer.py`.

## Host data directory

The compose file mounts `${WAKE_TRAINING_HOST_DATA_DIR:-../../data/wake-training}` into the container at `/data/wake-training` with `:rw` permissions. This ensures the Jetson can persist datasets, training artifacts, and deployment bundles in a location the host (and CI) can inspect.

The repository includes a matching `data/wake-training/` directory (with a `.gitkeep` placeholder). If you want to use a different path on the Jetson, export `WAKE_TRAINING_HOST_DATA_DIR=/absolute/host/path` before running compose.

## Usage

```bash
cd server/wake-training
# Optional: override defaults for Jetson builds
export WAKE_TRAINING_BASE_IMAGE=nvcr.io/nvidia/l4t-ml:r36.2.0-py3
export WAKE_TRAINING_HOST_DATA_DIR=/opt/wake-training-data
mkdir -p "$WAKE_TRAINING_HOST_DATA_DIR"

# Build and start the container (runs uvicorn on port 8080)
docker compose up --build -d

# Allow additional browser origins (comma separated)
export WAKE_TRAINING_CORS_ORIGINS=http://localhost:5173,http://192.168.7.217:5173
docker compose up --build -d
```

### Cross-origin access

When serving the Vue console from a different host, configure the allowed origins via `WAKE_TRAINING_CORS_ORIGINS` (comma separated). The default allows `http://localhost:5173` and `http://127.0.0.1:5173` for local development.

```bash
export WAKE_TRAINING_CORS_ORIGINS=http://localhost:5173,http://192.168.7.1:4173
```

### Training workflow

1. Create a dataset (`POST /datasets`) and upload labeled clips via `POST /datasets/{name}/recordings`. The trainer expects a minimum of ~10 wake clips and 10 non-wake/noise clips; more data yields better results.
2. Trigger training with `POST /train` and optional `config_overrides`. The job runner executes a PyTorch CNN, performs augmentation, computes validation metrics, and exports artifacts (`.pt`, ONNX, TorchScript, metrics/config JSON) under `/data/wake-training/jobs/<job_id>/export`.
3. Monitor progress through `/jobs/{job_id}` and `/jobs/{job_id}/logs` or subscribe to `ws://.../ws/events`.
4. Download artifacts or hand them to the deployment bridge (coming soon) to distribute to the Orange Pi runtime.

### API endpoints

- `GET /health` – basic status + resolved data root path.
- `GET /datasets` – list datasets with clip counts and creation time.
- `POST /datasets` – create a new dataset directory. Existing names return HTTP 409.
- `GET /datasets/{name}` – fetch dataset metadata.
- `POST /datasets/{name}/recordings` – upload WAV clips with `label` (`positive`, `negative`, `noise`).
- `DELETE /datasets/{name}/recordings/{clip_id}` – soft-delete a clip (moves it to `trash/`).
- `POST /datasets/{name}/recordings/{clip_id}/restore` – restore a deleted clip.
- `PATCH /datasets/{name}/recordings/{clip_id}` – update labels/notes.
- `GET /datasets/{name}/metrics` – aggregated clip counts by label.
- `POST /train` – enqueue a training job (`config_overrides` accepted).
- `GET /jobs/{job_id}` – fetch job status and exported artifact metadata.
- `GET /jobs/{job_id}/logs` – stream structured training logs.
- `GET /ws/events` – WebSocket stream of dataset + job events (ready for the Vue dashboard).

### Dependencies

- PyTorch 2.2 + TorchScript/ONNX export.
- NumPy/SciPy for resampling and augmentation.
- SoundFile (libsndfile) for WAV decoding.

On Jetson hardware you may want to build a wheel that matches the installed CUDA/cuDNN stack (override `requirements.txt` pins accordingly).

## Next steps

1. Extract the trainer into a dedicated GPU worker container and add job queue persistence.
2. Wire the deployment bridge to copy exported models to the Orange Pi and trigger hotword refresh.
3. Surface richer dataset QA (duration histograms, loudness, per-speaker stats) in the UI.
4. Add configurable hyperparameter presets via environment variables and expose them through the API.
