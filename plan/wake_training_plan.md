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

Deployment: docker compose bundle tailored for Jetson (arm64 + CUDA base). Compose mounts `./data/wake-training` (host) to `/data` in containers to satisfy the “accessible by host” requirement.

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
- `GET /datasets` → summary metrics.
- `POST /datasets` → create dataset (default `tars-default`).
- `GET /datasets/{id}` → detailed stats + last job summary.
- `POST /datasets/{id}/recordings` (multipart audio + metadata JSON).
- `DELETE /recordings/{clip_id}` → soft delete (flag in metadata).
- `PATCH /recordings/{clip_id}` → update label/notes.
- `POST /train` → `{ dataset_id, config_overrides? }` returns job id.
- `GET /jobs/{job_id}` → status snapshot.
- `GET /jobs/{job_id}/logs` → streaming log tail.
- `POST /deploy` → `{ job_id | artifact_path }` triggers transfer to Orange Pi.
- WebSocket `ws://.../status` → emits dataset updates, job stage transitions, transfer results.

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

## 13) Open Questions / Risks
- Do we need multi-speaker labeling (tag by user) for future personalization? (Impacts schema.)
- Is Orange Pi resource-constrained for TensorRT inference, or do we fallback to ONNXRuntime CPU?
- Will the Jetson remain dedicated for training, or also run other services (affects GPU contention)?
- Should we support incremental learning (continue training using previous checkpoint) vs always retraining?
- Network constraints: ensure Orange Pi reachable over SSH; consider offline deployment fallback (USB export).
