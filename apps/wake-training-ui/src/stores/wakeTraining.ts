import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { http, websocketUrl } from "@/lib/apiClient";
import type {
  DatasetEvent,
  DatasetMetrics,
  DatasetSummary,
  JobLogChunk,
  JobLogEntry,
  TrainingJob,
} from "@/types/wakeTraining";

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

type JobStatus = TrainingJob["status"];

export interface DatasetRecord {
  name: string;
  createdAt: string;
  clipCount: number;
  totalDurationSec: number;
  positives: number;
  negatives: number;
  noise: number;
  deletedClips?: number;
}

export interface JobRecord {
  id: string;
  dataset: string;
  status: JobStatus;
  updatedAt: string;
  error?: string | null;
  config?: Record<string, unknown>;
}

export interface JobLogDisplay {
  jobId: string;
  dataset: string;
  status: JobStatus;
  entries: JobLogEntry[];
}

export const useWakeTrainingStore = defineStore("wakeTraining", () => {
  const datasets = ref<Record<string, DatasetRecord>>({});
  const jobs = ref<Record<string, JobRecord>>({});
  const jobLogs = ref<Record<string, JobLogEntry[]>>({});
  const jobLogOffsets = ref<Record<string, number>>({});

  const connectionStatus = ref<ConnectionStatus>("disconnected");
  const loadingDatasets = ref<boolean>(false);
  const lastError = ref<string | null>(null);
  const lastUploadError = ref<string | null>(null);
  const uploadingRecording = ref<boolean>(false);

  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let manualClose = false;

  async function loadDatasets(): Promise<void> {
    loadingDatasets.value = true;
    try {
      const { data } = await http.get<DatasetSummary[]>("/datasets");
      const metricPromises = data.map(async (summary: DatasetSummary) => {
        const metrics = await fetchMetrics(summary.name);
        upsertDataset(summary, metrics);
      });
      await Promise.allSettled(metricPromises);
    } catch (error) {
      lastError.value = parseError(error);
    } finally {
      loadingDatasets.value = false;
    }
  }

  async function fetchMetrics(dataset: string): Promise<DatasetMetrics | null> {
    try {
      const { data } = await http.get<DatasetMetrics>(`/datasets/${dataset}/metrics`);
      return data;
    } catch (error) {
      lastError.value = parseError(error);
      return null;
    }
  }

  async function uploadRecording(
    dataset: string,
    blob: Blob,
    options: {
      label: string;
      speaker?: string;
      notes?: string;
    },
  ): Promise<void> {
    uploadingRecording.value = true;
    lastUploadError.value = null;
    try {
      const filename = `${dataset}-${Date.now()}.wav`;
      const formData = new FormData();
      formData.append("file", blob, filename);
      formData.append("label", options.label);
      if (options.speaker) {
        formData.append("speaker", options.speaker);
      }
      if (options.notes) {
        formData.append("notes", options.notes);
      }

      await http.post(`/datasets/${dataset}/recordings`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const metrics = await fetchMetrics(dataset);
      if (metrics) {
        applyMetrics(metrics);
      }
    } catch (error) {
      const message = parseError(error);
      lastUploadError.value = message;
      lastError.value = message;
      throw error;
    } finally {
      uploadingRecording.value = false;
    }
  }

  function upsertDataset(summary: DatasetSummary, metrics: DatasetMetrics | null): void {
    const existing = datasets.value[summary.name] ?? {
      positives: 0,
      negatives: 0,
      noise: 0,
      clipCount: summary.clip_count,
      totalDurationSec: summary.total_duration_sec,
      createdAt: summary.created_at,
      name: summary.name,
      deletedClips: summary.deleted_clips,
    };

    const resolved: DatasetRecord = {
      ...existing,
      name: summary.name,
      createdAt: summary.created_at,
      clipCount: metrics?.clip_count ?? summary.clip_count ?? existing.clipCount,
      totalDurationSec: metrics?.total_duration_sec ?? summary.total_duration_sec ?? existing.totalDurationSec,
      positives: metrics?.positives ?? existing.positives,
      negatives: metrics?.negatives ?? existing.negatives,
      noise: metrics?.noise ?? existing.noise,
      deletedClips: summary.deleted_clips ?? existing.deletedClips,
    };

    datasets.value[summary.name] = resolved;
  }

  function applyMetrics(metrics: DatasetMetrics): void {
    const current = datasets.value[metrics.name];
    const next: DatasetRecord = {
      name: metrics.name,
      createdAt: current?.createdAt ?? new Date().toISOString(),
      clipCount: metrics.clip_count,
      totalDurationSec: metrics.total_duration_sec,
      positives: metrics.positives,
      negatives: metrics.negatives,
      noise: metrics.noise,
      deletedClips: current?.deletedClips,
    };
    datasets.value[metrics.name] = next;
  }

  async function refreshJob(jobId: string, dataset: string): Promise<void> {
    try {
      const { data } = await http.get<TrainingJob>(`/jobs/${jobId}`);
      jobs.value[jobId] = {
        id: data.id,
        dataset: data.dataset,
        status: data.status,
        updatedAt: data.updated_at,
        error: data.error ?? null,
        config: data.config,
      };
    } catch (error) {
      // if the job record disappeared, keep the last known status but note error
      const existing = jobs.value[jobId];
      if (!existing) {
        jobs.value[jobId] = {
          id: jobId,
          dataset,
          status: "failed",
          updatedAt: new Date().toISOString(),
          error: parseError(error),
        };
      }
      lastError.value = parseError(error);
    }
  }

  function handleLogChunk(chunk: JobLogChunk): void {
    const knownOffset = jobLogOffsets.value[chunk.job_id] ?? 0;
    if (chunk.next_offset <= knownOffset && chunk.entries.length === 0) {
      return;
    }
    if (chunk.next_offset <= knownOffset && chunk.entries.length > 0) {
      // duplicate delivery; skip
      return;
    }
    const existing = jobLogs.value[chunk.job_id] ?? [];
    const merged: JobLogEntry[] = [...existing, ...chunk.entries];
    jobLogs.value[chunk.job_id] = merged.slice(-200);
    jobLogOffsets.value[chunk.job_id] = chunk.next_offset;
  }

  function handleEvent(event: DatasetEvent): void {
    applyMetrics(event.metrics);

    switch (event.type) {
      case "dataset.created":
      case "recording.uploaded":
      case "recording.deleted":
      case "recording.restored":
      case "recording.updated":
        // metrics already applied
        break;
      case "job.queued":
      case "job.running":
      case "job.completed":
      case "job.failed":
        if (event.job_id) {
          void refreshJob(event.job_id, event.dataset);
        }
        break;
      case "job.log":
        if (event.log_chunk) {
          handleLogChunk(event.log_chunk);
        }
        if (event.job_id) {
          const known = jobs.value[event.job_id];
          if (!known) {
            void refreshJob(event.job_id, event.dataset);
          }
        }
        break;
      default:
        break;
    }
  }

  function connectEvents(): void {
    if (socket || reconnectTimer) {
      return;
    }
    manualClose = false;
    connectionStatus.value = "connecting";
    lastError.value = null;

    try {
      const ws = new WebSocket(websocketUrl("/ws/events"));
      socket = ws;

      ws.addEventListener("open", () => {
        connectionStatus.value = "connected";
        ws.send(
          JSON.stringify({
            source: "wake-training-ui",
            ts: new Date().toISOString(),
          })
        );
      });

      ws.addEventListener("message", (event) => {
        try {
          const payload = JSON.parse(event.data) as DatasetEvent;
          handleEvent(payload);
        } catch (error) {
          lastError.value = parseError(error);
        }
      });

      ws.addEventListener("error", (event) => {
        console.error("Wake training WS error", event);
        connectionStatus.value = "error";
        lastError.value = "WebSocket error";
      });

      ws.addEventListener("close", () => {
        socket = null;
        if (manualClose) {
          connectionStatus.value = "disconnected";
          return;
        }
        connectionStatus.value = "disconnected";
        scheduleReconnect();
      });
    } catch (error) {
      lastError.value = parseError(error);
      scheduleReconnect();
    }
  }

  function scheduleReconnect(): void {
    if (reconnectTimer) {
      return;
    }
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectEvents();
    }, 5000);
  }

  function disconnectEvents(): void {
    manualClose = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      socket.close(1000, "client disconnect");
      socket = null;
    }
    connectionStatus.value = "disconnected";
  }

  const datasetList = computed<DatasetRecord[]>(() =>
    (Object.values(datasets.value) as DatasetRecord[]).sort((a, b) =>
      a.name.localeCompare(b.name)
    )
  );

  const jobList = computed<JobRecord[]>(() =>
    (Object.values(jobs.value) as JobRecord[]).sort((a, b) =>
      b.updatedAt.localeCompare(a.updatedAt)
    )
  );

  const jobLogsList = computed<JobLogDisplay[]>(() =>
    jobList.value.map((job: JobRecord) => ({
      jobId: job.id,
      dataset: job.dataset,
      status: job.status,
      entries: jobLogs.value[job.id] ?? [],
    }))
  );

  return {
  datasetList,
  jobList,
  jobLogsList,
    connectionStatus,
    loadingDatasets,
    lastError,
    lastUploadError,
    uploadingRecording,
    loadDatasets,
    uploadRecording,
    connectEvents,
    disconnectEvents,
  };
});

function parseError(error: unknown): string {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message ?? "Unknown error");
  }
  return "Unknown error";
}
