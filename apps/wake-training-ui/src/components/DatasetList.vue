<script setup lang="ts">
import type { DatasetRecord } from "@/stores/wakeTraining";

const props = defineProps<{
  datasets: DatasetRecord[];
  loading: boolean;
}>();

const formatter = new Intl.NumberFormat();
const secondsFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 1,
});

function durationLabel(seconds: number): string {
  if (!seconds) return "0s";
  if (seconds > 3600) {
    return `${secondsFormatter.format(seconds / 3600)} h`;
  }
  if (seconds > 60) {
    return `${secondsFormatter.format(seconds / 60)} min`;
  }
  return `${secondsFormatter.format(seconds)} s`;
}
</script>

<template>
  <section class="card">
    <header class="section-header">
      <div>
        <h2>Datasets</h2>
        <p class="subtitle">Live clip counts and balance across wake/noise classes.</p>
      </div>
      <span class="badge" v-if="loading">Refreshing…</span>
    </header>

    <table class="table" v-if="datasets.length">
      <thead>
        <tr>
          <th>Name</th>
          <th>Clips</th>
          <th>Positives</th>
          <th>Negatives</th>
          <th>Noise</th>
          <th>Duration</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="dataset in datasets" :key="dataset.name">
          <td>{{ dataset.name }}</td>
          <td>{{ formatter.format(dataset.clipCount) }}</td>
          <td>{{ formatter.format(dataset.positives) }}</td>
          <td>{{ formatter.format(dataset.negatives) }}</td>
          <td>{{ formatter.format(dataset.noise) }}</td>
          <td>{{ durationLabel(dataset.totalDurationSec) }}</td>
        </tr>
      </tbody>
    </table>

    <p v-else class="empty-state">No datasets yet. Upload audio from the Pi to see activity.</p>
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

.empty-state {
  margin: 1.25rem 0 0;
  color: rgba(148, 163, 184, 0.75);
}
</style>
