export type DatasetEventType =
  | "dataset.created"
  | "dataset.updated"
  | "dataset.deleted"
  | "recording.uploaded"
  | "recording.deleted"
  | "recording.restored"
  | "recording.updated"
  | "job.queued"
  | "job.running"
  | "job.completed"
  | "job.failed"
  | "job.log";

export interface DatasetSummary {
  name: string;
  created_at: string;
  clip_count: number;
  total_duration_sec: number;
  description?: string | null;
  deleted_clips?: number;
}

export interface DatasetMetrics {
  name: string;
  clip_count: number;
  total_duration_sec: number;
  positives: number;
  negatives: number;
  noise: number;
}

export interface DatasetDetail extends DatasetSummary {
  deleted_clips: number;
  path: string;
}

export interface TrainingJob {
  id: string;
  dataset: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  config: Record<string, unknown>;
  error?: string | null;
}

export interface JobLogEntry {
  timestamp: string;
  message: string;
  raw: string;
}

export interface JobLogChunk {
  job_id: string;
  offset: number;
  next_offset: number;
  total_size: number;
  has_more: boolean;
  entries: JobLogEntry[];
}

export interface DatasetEvent {
  type: DatasetEventType;
  dataset: string;
  metrics: DatasetMetrics;
  timestamp: string;
  previous_dataset?: string;
  clip_id?: string;
  job_id?: string;
  log_chunk?: JobLogChunk;
}
