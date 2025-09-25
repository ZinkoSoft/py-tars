<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref, watch } from "vue";
import DatasetList from "@/components/DatasetList.vue";
import JobStatusCards from "@/components/JobStatusCards.vue";
import JobLogViewer from "@/components/JobLogViewer.vue";
import RecorderPanel from "@/components/RecorderPanel.vue";
import { useWakeTrainingStore } from "@/stores/wakeTraining";

const store = useWakeTrainingStore();
const showRecorder = ref(false);

const apiHost = computed(() => {
  const baseUrl = __API_BASE_URL__;
  const UrlCtor = globalThis.URL;
  if (typeof UrlCtor === "function") {
    try {
      return new UrlCtor(baseUrl).host;
    } catch {
      /* fall through */
    }
  }
  return baseUrl;
});

onMounted(() => {
  void store.loadDatasets();
  store.connectEvents();
});

onUnmounted(() => {
  store.disconnectEvents();
});

watch(
  () => store.datasetList.length,
  (count) => {
    if (count === 0) {
      showRecorder.value = true;
    }
  },
  { immediate: true },
);

function toggleRecorder(): void {
  showRecorder.value = !showRecorder.value;
}
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
        <button class="primary" type="button" @click="toggleRecorder">
          {{ showRecorder ? "Hide capture panel" : "Capture new audio" }}
        </button>
        <span class="badge">API: {{ apiHost }}</span>
        <span class="badge" v-if="store.lastError">Last error: {{ store.lastError }}</span>
      </div>
    </header>

    <main class="layout">
      <section class="layout-primary">
        <transition name="slide-fade">
          <RecorderPanel
            v-if="showRecorder"
            class="layout-recorder"
            :datasets="store.datasetList"
            :loading="store.loadingDatasets"
          />
        </transition>
        <DatasetList :datasets="store.datasetList" :loading="store.loadingDatasets" />
      </section>
      <aside class="layout-sidebar">
        <JobStatusCards :jobs="store.jobList" :status="store.connectionStatus" :error="store.lastError" />
        <JobLogViewer :logs="store.jobLogsList" />
      </aside>
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
  align-items: center;
  gap: 0.75rem;
}

.primary {
  border-radius: 999px;
  padding: 0.45rem 1.4rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.35), rgba(59, 130, 246, 0.45));
  border: 1px solid rgba(37, 99, 235, 0.65);
  color: #f8fafc;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 1.75rem;
  align-items: start;
}

.layout-primary {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.layout-sidebar {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.layout-recorder {
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.45);
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.25s ease;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}

@media (max-width: 1200px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .layout-sidebar {
    order: -1;
  }
}

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-meta {
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
  .hero-meta {
    width: 100%;
    gap: 0.5rem;
  }

  .primary {
    width: 100%;
    text-align: center;
  }
}
</style>
