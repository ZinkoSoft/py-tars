# Wake Word Training Service Plan

Goal: deliver a GPU-accelerated workflow for collecting wake-phrase audio, training a custom hotword detector on the Jetson Orin Nano, and deploying the resulting model to the Orange Pi TARS stack with minimal operator effort.

## 1) Objectives
- Provide a hosted training surface that stores, curates, and audits wake-word recordings.
- Expose a simple web UI that surfaces dataset health (clip counts, duration, noise levels), supports review/discard, and launches training.
- Exploit the Jetson Orin GPU to fine-tune a neural keyword-spotting (KWS) model in minutes.
- Export trained artifacts to a host-accessible directory with versioned metadata.
- Allow a single click to ship the trained model to the Orange Pi and trigger the relevant TARS services to adopt it.

## 2) Platform & Components
| Component | Purpose | Tech | Notes |
| --- | --- | --- | --- |
| `training-api` | REST/WebSocket control plane, dataset management | FastAPI (Python 3.11) | Runs on Jetson; talks to storage + job queue |
| `training-worker` | GPU training + evaluation jobs | PyTorch + NVIDIA NeMo, TorchAudio | Runs as separate process/container with CUDA enabled |
| `recording-ingestor` | Optional helper for live mic capture from LAN | WebRTC/WebSocket bridge | Streams audio to training-api |
| `training-ui` | Browser UI for operators | React/Vite or FastAPI templates | Hosted by training-api or standalone |
| `artifact-registry` | File store for datasets & models | Host volume (`/data/wake-training`) | Mounted read/write inside Jetson containers |
| `transfer-agent` | Handles “Apply to TARS” deployment | Paramiko/rsync/SSH | Needs Orange Pi credentials & target path |

Deployment: docker compose bundle tailored for Jetson (arm64 + CUDA base). The repository now hosts initial scaffolding under `server/wake-training/` (Dockerfile, compose, README). The compose defaults map `${WAKE_TRAINING_HOST_DATA_DIR:-../../data/wake-training}` on the host to `/data/wake-training` in-container, satisfying the “accessible by host” requirement while allowing overrides for real hardware paths.

## 3) Storage Layout
```
/data/wake-training/
  datasets/
    <dataset_id>/
      clips/
        <uuid>.wav
      labels.json               # metadata, quality flags, speaker tags
      metrics.json              # SNR, duration stats, last reviewer
  jobs/
    <job_id>/
      config.json
      logs.txt
      checkpoints/
      export/
        wake_model.onnx
        wake_model.trt           # optional TensorRT engine
        metadata.json            # thresholds, accuracy, date
        confusion_matrix.png
  scratch/                      # temporary augmented clips
  transfers/
    <timestamp>-model.tar.gz     # bundles staged for Orange Pi

Repo note: `data/wake-training/` (with `.gitkeep`) seeds the host directory for local development; Jetson deployments should bind-mount the actual persistent path defined by `WAKE_TRAINING_HOST_DATA_DIR`.
```

## 4) Data Flow
1. Operator records or uploads wake/noise clips via UI → `POST /datasets/{id}/recordings`.
2. API stores audio, runs background feature extraction (duration, peak levels), updates metrics cache.
3. UI polls or receives WS updates with clip counts, reveals discard controls.
4. Operator trims dataset (delete/relabel). When satisfied, hits **Train**.
5. API enqueues a `training-worker` job; worker pulls dataset, performs augmentation, fine-tunes base model on GPU, evaluates, exports ONNX + TensorRT.
6. Job metadata is persisted and emitted over WebSocket for UI progress.
7. Operator clicks **Apply training to TARS** → API bundles latest artifact, transfers via SSH/SCP to Orange Pi drop folder, triggers remote script to swap model and restart wake service.

## 5) UI / UX Requirements
- Dashboard cards per dataset: total clips, minutes, positive vs negative balance, last trained model accuracy.
- Recording table with sortable columns (speaker, date, length, quality score) and inline delete/restore.
- Waveform preview + playback for QA (use wavesurfer.js).
- Buttons:
  - `Record` (WebAudio) → allows tagging (positive/negative/noise) before upload.
  - `Upload` (drag/drop) for importing WAVs.
  - `Discard` / `Restore` to manage dataset hygiene.
  - `Train` (disabled unless dataset meets minimum clip count, e.g., ≥50 positive, ≥50 negative).
  - `Apply training to TARS` (enabled once latest job succeeded).
- Training status modal: progress bar (data prep → training → eval → export), GPU telemetry, estimated remaining time.
- Notification area for success/failure with download link to artifacts.

## 6) API Surface (initial draft)
- `GET /datasets` → summary metrics. (Implemented)
- `POST /datasets` → create dataset (default `tars-default`). (Implemented)
- `GET /datasets/{id}` → detailed stats + last job summary. (Implemented)
- `POST /datasets/{id}/recordings` (multipart audio + metadata JSON). (Implemented)
- `DELETE /datasets/{id}/recordings/{clip_id}` → soft delete (move to trash, mark in labels). (Implemented; returns 200 with `{ "status": "ok" }`)
- `POST /datasets/{id}/recordings/{clip_id}/restore` → undo soft delete. (Implemented; returns 200 with `{ "status": "ok" }`)
- `PATCH /datasets/{id}/recordings/{clip_id}` → update label/notes. (Implemented)
- `POST /train` → `{ dataset_id, config_overrides? }` returns job id. (Implemented)
- `GET /jobs/{job_id}` → status snapshot. (Implemented)
- `GET /jobs/{job_id}/logs` → streaming log tail. (Planned)
- `POST /deploy` → `{ job_id | artifact_path }` triggers transfer to Orange Pi. (Planned)
- WebSocket `ws://.../status` → emits dataset updates, job stage transitions, transfer results. (Planned)

Note on responses: For delete/restore we use HTTP 200 with a tiny JSON body instead of 204 to avoid FastAPI constraints on 204-with-body across versions.

## 7) Training Pipeline (GPU focus)
1. **Pre-flight checks**: ensure dataset balance, compute class weights, run VAD to prune silence.
2. **Augmentation**: mix with background noise, pitch/time shift, random gain. Cache augmented versions in `/data/wake-training/scratch`.
3. **Model**: fine-tune NVIDIA NeMo MarbleNet (keyword spotting) with PyTorch Lightning; fallback to openwakeword if NeMo unavailable.
4. **GPU utilization**: use CUDA mixed precision (AMP), set data loader num-workers to leverage Jetson GPU + CPU.
5. **Evaluation**: split 80/20 train/val; compute ROC curves, false accept vs false reject at multiple thresholds.
6. **Export**:
   - Save PyTorch checkpoint.
   - Export ONNX (dynamic batch × 1 sec input) for compatibility.
   - Optionally build TensorRT engine for low-latency inference on Jetson (for future deployment).
   - Generate `metadata.json` with threshold recommendations, accuracy metrics, dataset provenance.
7. **Threshold selection**: pick operating point that meets target false alarm rate (e.g., <=1/min) and record in metadata.

## 8) Artifact Versioning & Host Access
- Each job writes to `/data/wake-training/jobs/<job_id>/export`.
- Latest “blessed” model is symlinked to `/data/wake-training/models/current` for easy mounting by other services.
- Host operator can inspect artifacts directly (volume is on Jetson but shared over NFS/Samba if needed).
- Keep a manifest (`artifacts.json`) summarizing lineage (dataset hash, augmentation config, accuracy).

## 9) "Apply to TARS" Deployment
- Env-driven remote config:
  - `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, optional `DEPLOY_SSH_KEY`.
  - Optional `DEPLOY_POST_COMMAND` (e.g., `systemctl restart stt-hotword`).
- Flow:
  1. Zip export directory to `/data/wake-training/transfers/<timestamp>.tar.gz`.
  2. SCP/rsync to Orange Pi `${DEPLOY_PATH}/incoming/`.
  3. SSH execute remote script (`deploy_hotword.sh`) that unpacks, atomically swaps symlink, restarts wake detector container/service, and publishes MQTT health.
  4. Capture stdout/stderr, surface result in UI.
- Handle retries + rollback: keep previous artifact zipped on remote; if deploy fails, revert and notify user.

## 10) Integration with TARS Runtime
- STT worker gains optional "external wake model" mode: load exported ONNX/TensorRT via `onnxruntime` or TensorRT runtime.
- Router wake logic remains unchanged; STT worker emits wake detection events (`stt/wake/{model_id}`) or injects wake phrase into transcript stream.
- Provide configuration toggle (`STT_WAKE_MODEL_PATH=/models/wake_model.onnx`).

## 11) Security, Observability & Ops
- Authentication: protect training UI/API with OAuth proxy or token (Jetson dashboard is internal but still require login).
- Rate limit uploads; validate audio MIME & duration.
- Persist audit trail: who deleted clip, who triggered training/deploy.
- Metrics: expose Prometheus endpoints for GPU utilization, job duration, dataset counts.
- Logging: structure logs (JSON) and ship to Loki/ELK.
- Backups: nightly rsync of `/data/wake-training` to NAS.

## 12) Milestones
1. **MVP Dataset Service**: API + storage layout + UI list/record/delete; manual training script.
2. **GPU Training Job**: Containerized training-worker, NeMo fine-tuning, artifact export.
3. **UI Integration**: Real-time progress, Train button gating, dataset health checks.
4. **Deployment Bridge**: Transfer-agent with retry/rollback, UI button + logs.
5. **STT Integration**: Update TARS STT worker to consume exported model, smoke test on Orange Pi.
6. **Polish**: Metrics, authentication, auto-cleanup of scratch space, multi-dataset support.

## 12b) Status Update (2025-09-24)

Completed (MVP slice):
- Training API scaffolded under `server/wake-training/` with health and dataset endpoints.
- Filesystem storage adapters: datasets directory layout, `clips/` folder, `labels.json` as authoritative metadata index.
- Recording ingestion endpoint (`POST /datasets/{id}/recordings`) with WAV + metadata validation.
- Curation endpoints: soft delete, restore, and metadata patch; implemented as:
  - `DELETE /datasets/{id}/recordings/{clip_id}` → moves file to `trash/`, sets `deleted_at`.
  - `POST /datasets/{id}/recordings/{clip_id}/restore` → moves back to `clips/`, clears `deleted_at`.
  - `PATCH /datasets/{id}/recordings/{clip_id}` → updates `label`/`speaker`/`notes`, sets `updated_at`.
- Unified repo test runner wired to include wake-training tests; service-level tests cover happy paths and error cases; current suite is green.
- Dataset metrics model and recomputation pipeline (`metrics.json`) with `/datasets/{id}/metrics` endpoint and coverage tests.
- Real-time dataset event hub (`/ws/events`) broadcasting create/upload/delete/restore/patch actions with WebSocket integration tests.
- Training job queue endpoints (`POST /train`, `GET /jobs/{job_id}`) with filesystem-backed persistence, WebSocket `job.queued` events, and API/WS test coverage.
- Training job runner error handling and failure path have been fully hardened and validated. All tests pass using the unified test runner (`run.tests.sh`). The runner now emits `job_failed` events with error context, and file corruption issues have been resolved. This closes the runner robustness milestone.
- Job log persistence API (`GET /jobs/{job_id}/logs`) now returns structured chunks with offsets/limits, and `job.log` WebSocket events stream live updates to the UI. Tests cover pagination and event payloads.

Out-of-scope/implementation deviations (documented):
- Standardized curation endpoints to return HTTP 200 `{ "status": "ok" }` (instead of 204) to maintain compatibility with FastAPI’s no-body-on-204 rule.
- Added an explicit restore endpoint in API surface (UI had Restore concept; API now matches it explicitly).
- Added unified `run.tests.sh` integration to automatically execute wake-training tests in CI/local runs.

Pending (near-term):
- Surface metrics & event stream in the UI (cards, clip table, notifications) and gate Train button via dataset health.
- Training job execution worker (GPU fine-tune) and deployment bridge to Orange Pi.
- **NEXT: Wake training frontend (Vue) consuming REST + WebSocket APIs for datasets, jobs, and logs.**
- Job progress WebSocket channel covering queued → running → completed/failed transitions with log tail support.
- UI wiring for job queue: Train button state, job list, progress modal consuming new endpoints/events.

## 13) Open Questions / Risks
- Do we need multi-speaker labeling (tag by user) for future personalization? (Impacts schema.)
- Is Orange Pi resource-constrained for TensorRT inference, or do we fallback to ONNXRuntime CPU?
- Will the Jetson remain dedicated for training, or also run other services (affects GPU contention)?
- Should we support incremental learning (continue training using previous checkpoint) vs always retraining?
- Network constraints: ensure Orange Pi reachable over SSH; consider offline deployment fallback (USB export).

## 14) Implementation Backlog (MVP-first)

### Sprint 0 – Environment bring-up
- [X] Provision Jetson Orin Nano base OS (JetPack) and enable CUDA + Docker runtime.
- [ ] Create `/data/wake-training` host directory with proper permissions and backup job (rsync to NAS). *(Repo-level seed at `data/wake-training/` complete; production mount + backup job pending.)*
- [ ] Generate SSH keys / credentials for Orange Pi deployment target; store in secrets vault.
- [X] Commit container scaffolding under `server/wake-training/` (Dockerfile, compose, README) with host RW volume mapping.

### Sprint 1 – Dataset service foundation
- [X] Scaffold `training-api` FastAPI project with health endpoint, dataset list/create/detail using local filesystem. *(Dataset delete not implemented yet.)*
- [X] Implement storage adapters (datasets/, clips/, labels.json). *(Background metrics worker pending.)*
- [x] Add WebSocket broadcaster for dataset change events. *(Training API now exposes `/ws/events` via `EventHub`; tests verify broadcasts.)*
- [ ] Stand up minimal Vite UI with dataset list + clip counter display.

### Sprint 2 – Recording ingestion & curation
- [ ] Add WebAudio/drag-drop upload flow with metadata tagging. *(API ingestion endpoint implemented; UI flow pending.)*
- [ ] Implement clip review table with delete/restore + waveform preview. *(API curation endpoints implemented: delete, restore, patch; UI pending.)*
- [ ] Introduce validation jobs (duration bounds, RMS/SNR scoring) and surface warnings in UI. *(Planned.)*

#### Guided wake-phrase recording flow (added 2025-09-24)
- **User story**: An operator wants the UI to walk them through capturing a wake phrase (e.g., "HELLO TARS") multiple times with countdown prompts so fresh WAV clips land directly in the dataset.
- **Experience outline**
  1. Select dataset + speaker context, confirm canonical phrase, choose positive/negative/noise target counts.
  2. Microphone permission check with live VU meter; show quick capture tips.
  3. Guided loop per take: display prompt ("Take N of M – Say 'HELLO TARS'"), 3→2→1 countdown, auto-record for configured window, playback & retry before keeping.
  4. After keeping, immediately POST WAV + metadata; advance to next take until targets satisfied, then prompt for negatives/noise or move to training.
  5. Session summary card tracks progress (positives recorded, retries, warnings) and links to dataset table for review.
- **Backend updates**
  - Extend `RecordingMetadata` to capture `phrase`, `attempt`, `session_id`, and `source` (`web_recorder` vs upload) while keeping label/speaker/notes intact.
  - Persist new metadata fields in `labels.json` and include them in dataset metrics/events; add tests covering serialization.
  - Optional QC: enforce clip duration bounds, compute RMS/clipping heuristic, return warnings in response to surface in UI.
- **Frontend work**
  - WebAudio recorder utility (16 kHz mono PCM → WAV blob) with countdown UI + waveform preview (wavesurfer.js or canvas).
  - Session controller storing target counts, progress, retries, and generating metadata payloads for `/datasets/{name}/recordings`.
  - Status toasts + progress panel; integrate with existing store so metrics update via WebSocket in real time.
  - Accessibility: keyboard shortcuts for retry/keep, visual cues for countdown, fallbacks if mic permission denied (show manual upload path).

### Sprint 3 – GPU training pipeline
- [ ] Containerize `training-worker` with CUDA base image and NeMo dependencies.
- [ ] Build job queue bridge (e.g., Redis + RQ or FastAPI TaskGroup) between API and worker. *(API now queues jobs in `/train`; worker + consumer pending.)*
- [ ] Implement training job: dataset split, augmentation, MarbleNet fine-tune, evaluation metrics.
- [ ] Export ONNX + metadata, persist logs/artifacts under `/data/wake-training/jobs/<job_id>/`.
- [ ] Emit real-time job progress events (Pub/Sub channel consumed by UI progress modal).

### Sprint 4 – Deploy-to-TARS pipeline
- [ ] Implement artifact packaging + checksum manifest.
- [ ] Build `transfer-agent` module (Paramiko/rsync) with retry + rollback logic.
- [ ] Create remote `deploy_hotword.sh` script template and document expected location on Orange Pi.
- [ ] Wire "Apply training" button in UI with confirmation dialog + status toasts.

### Sprint 5 – Integration & hardening
- [ ] Update STT worker to load external wake model and expose configuration flag.
- [ ] Add automated smoke test that runs exported model against validation clips.
- [ ] Instrument Prometheus metrics (dataset counts, GPU utilization, job durations, deploy outcomes).
- [ ] Gate API/UI behind auth proxy (JWT/OIDC) and enable audit logging.
- [ ] Implement artifact lifecycle management (auto-prune scratch/, retain last N models).

### Immediate Next Steps
1. Confirm Jetson OS + CUDA versions we target; document in repo `plan/`.
2. Decide on job queue technology (RQ vs Celery vs FastAPI background tasks) and reflect in requirements.
3. Draft interface contract for STT worker hotword loader so training artifacts match expected format.
4. Finalize Jetson host storage mount for `/data/wake-training`, add rsync backup job, and record the path in infra docs.
5. **Scaffold dedicated wake-training Vue UI under `apps/`, document API base URL env, and consume dataset/job/log endpoints.**
6. Start remaining Sprint 0 tasks; capture status updates in this plan file.
