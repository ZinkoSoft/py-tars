# Docker & Compose Guide (Single docker/ folder)

## What you get
- **One reusable Dockerfile**: `docker/app.Dockerfile` builds ANY app by passing `APP_PATH` and `APP_MODULE`.
- **One compose file**: `ops/compose.yaml` starts Mosquitto + Router + TTS + STT.
- Clean caching: only the selected app’s sources are copied into the image at build time.

## How to run
```bash
docker compose -f ops/compose.yaml up --build
```

## Add a new app
1. Create `apps/my-worker/` with `pyproject.toml` and `src/my_worker/...` (console script optional).
2. Add a service block to `ops/compose.yaml`:
   ```yaml
   myworker:
     build:
       context: ..
       dockerfile: docker/app.Dockerfile
       args:
         PY_VERSION: "3.11"
         APP_PATH: apps/my-worker
         CONTRACTS_PATH: packages/tars-contracts
         APP_MODULE: my_worker.app_main
     image: tars/myworker:dev
     environment:
       MQTT_HOST: mqtt
       MQTT_PORT: "1883"
     depends_on:
       mqtt:
         condition: service_healthy
     command: ["sh","-lc","python -m my_worker.app_main"]
     restart: unless-stopped
   ```

## Best practices
- **Console scripts**: define `[project.scripts]` in each app’s `pyproject.toml`; then Compose can simply `command: ["tars-router"]`.
- **Contracts as wheels**: the Dockerfile builds **contracts** and the **selected app** into wheels for reproducible installs.
- **Small runtime**: multi-stage build avoids dev deps in the final image.
- **Config via env**: use `env_file:` per app (`apps/<app>/.env`), keep secrets out of Git.
- **Profiles**: use Compose `profiles` to run subsets (e.g., only `router` + `mqtt` during UI dev).
- **Retry on connect**: apps should retry MQTT until available (removes strict health ordering).
- **Volumes**: mount model/voice assets read-only; avoid baking big assets into the image unless necessary.
- **Separate base** *(optional)*: create `docker/base.Dockerfile` for libs (alsa, ffmpeg) and `FROM tars/python-base` in `app.Dockerfile`.

## Switching to per-app Dockerfiles (if desired later)
Keep `docker/` the single folder, but add more files:
- `docker/router.Dockerfile`
- `docker/tts.Dockerfile`
- `docker/stt.Dockerfile`
Then set `dockerfile:` per service. Reuse a shared `base.Dockerfile` with `FROM`.

---

This setup gives you a single **docker/** folder, one **compose** file, and repeatable builds for every app with minimal duplication.
