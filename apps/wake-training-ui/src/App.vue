<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";

import DatasetList from "@/components/DatasetList.vue";
import JobStatusCards from "@/components/JobStatusCards.vue";
import JobLogViewer from "@/components/JobLogViewer.vue";
import { useWakeTrainingStore } from "@/stores/wakeTraining";

const store = useWakeTrainingStore();

onMounted(() => {
  void store.loadDatasets();
  store.connectEvents();
});

onUnmounted(() => {
  store.disconnectEvents();
});
</script>

<template>
  <div class="container">
    <header class="hero">
      <div>
        <h1>TARS Wake Training Console</h1>
        <p class="tagline">
          Monitor datasets, follow GPU jobs, and tail logs while your Raspberry Pi streams audio captures.
        </p>
      </div>
      <div class="hero-meta">
        <span class="badge">API: {{ new URL(__API_BASE_URL__).host }}</span>
        <span class="badge" v-if="store.lastError">Last error: {{ store.lastError }}</span>
      </div>
    </header>

    <main class="grid">
      <DatasetList :datasets="store.datasetList" :loading="store.loadingDatasets" />
      <JobStatusCards :jobs="store.jobList" :status="store.connectionStatus" :error="store.lastError" />
      <JobLogViewer :logs="store.jobLogsList" />
    </main>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.75rem;
  margin-bottom: 2rem;
}

.hero h1 {
  margin: 0;
  font-size: 2.25rem;
}

.tagline {
  margin: 0.75rem 0 0;
  color: rgba(226, 232, 240, 0.75);
}

.hero-meta {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-meta {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
