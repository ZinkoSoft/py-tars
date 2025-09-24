<script setup lang="ts">
import type { JobLogDisplay } from "@/stores/wakeTraining";

const props = defineProps<{
  logs: JobLogDisplay[];
}>();
</script>

<template>
  <section class="card">
    <header class="section-header">
      <div>
        <h2>Job Logs</h2>
        <p class="subtitle">Live tail of the most recent training jobs.</p>
      </div>
    </header>

    <template v-if="logs.length">
      <article v-for="entry in logs" :key="entry.jobId" class="log-card">
        <header class="log-header">
          <div>
            <span class="log-job">Job {{ entry.jobId.slice(0, 8) }}</span>
            <span class="log-dataset">on {{ entry.dataset }}</span>
          </div>
          <span class="status-pill" :class="`status-${entry.status}`">{{ entry.status }}</span>
        </header>
        <pre class="code-block">
<span v-for="line in entry.entries" :key="line.timestamp + line.message">
[{{ new Date(line.timestamp).toLocaleTimeString() }}] {{ line.message }}
</span>
        </pre>
      </article>
    </template>

    <p v-else class="empty-state">No logs yet. Once a job starts this view streams log lines in real time.</p>
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

.log-card {
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.log-job {
  font-weight: 600;
  margin-right: 0.35rem;
}

.log-dataset {
  color: rgba(148, 163, 184, 0.75);
}

.status-pill {
  border-radius: 999px;
  padding: 0.25rem 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.25);
  text-transform: capitalize;
}

.empty-state {
  margin-top: 1.25rem;
  color: rgba(148, 163, 184, 0.75);
}
</style>
