<script setup lang="ts">
import type { JobRecord } from "@/stores/wakeTraining";

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

const props = defineProps<{
  jobs: JobRecord[];
  status: ConnectionStatus;
  error: string | null;
}>();

const statusLabels: Record<JobRecord["status"], string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

function statusClass(status: JobRecord["status"]): string {
  switch (status) {
    case "completed":
      return "status-ready";
    case "running":
      return "status-running";
    case "failed":
      return "status-failed";
    default:
      return "status-queued";
  }
}
</script>

<template>
  <section class="card">
    <header class="section-header">
      <div>
        <h2>Training Jobs</h2>
        <p class="subtitle">Streamed from the Jetson runner via WebSocket.</p>
      </div>
      <span class="badge" :class="props.status">
        <template v-if="props.status === 'connected'">Live feed</template>
        <template v-else-if="props.status === 'connecting'">Connecting…</template>
        <template v-else-if="props.status === 'error'">Feed error</template>
        <template v-else>Offline</template>
      </span>
    </header>

    <p v-if="props.error" class="error">{{ props.error }}</p>

    <div class="job-grid" v-if="jobs.length">
      <article class="job-card" v-for="job in jobs" :key="job.id">
        <header>
          <span class="job-id">{{ job.id.slice(0, 8) }}</span>
          <span class="status" :class="statusClass(job.status)">{{ statusLabels[job.status] }}</span>
        </header>
        <p class="job-dataset">Dataset: <strong>{{ job.dataset }}</strong></p>
        <ul class="meta">
          <li>
            <span class="label">Updated</span>
            <span>{{ new Date(job.updatedAt).toLocaleString() }}</span>
          </li>
          <li v-if="job.error">
            <span class="label">Error</span>
            <span class="error">{{ job.error }}</span>
          </li>
        </ul>
      </article>
    </div>

    <p v-else class="empty-state">Launch a training job to see activity here.</p>
  </section>
</template>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.subtitle {
  margin: 0.1rem 0 0;
  color: rgba(226, 232, 240, 0.75);
}

.error {
  margin: 0.5rem 0;
  color: #f87171;
}

.job-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  margin-top: 1.25rem;
}

.job-card {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.job-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
}

.job-id {
  font-family: "Fira Code", "JetBrains Mono", monospace;
  color: rgba(148, 163, 184, 0.85);
}

.status {
  font-weight: 600;
}

.job-dataset {
  margin: 0;
}

.meta {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
}

.meta .label {
  color: rgba(148, 163, 184, 0.65);
  margin-right: 0.35rem;
}

.empty-state {
  margin-top: 1.25rem;
  color: rgba(148, 163, 184, 0.75);
}
</style>
