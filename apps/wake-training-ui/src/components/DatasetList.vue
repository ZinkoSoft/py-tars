<script setup lang="ts">
import { ref } from "vue";
import { useWakeTrainingStore } from "@/stores/wakeTraining";
import type { DatasetRecord } from "@/stores/wakeTraining";

const props = defineProps<{
  datasets: DatasetRecord[];
  loading: boolean;
}>();

type BusyFlags = {
  rename?: boolean;
  delete?: boolean;
  train?: boolean;
};

const store = useWakeTrainingStore();

const formatter = new Intl.NumberFormat();
const secondsFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const createdFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const editingDataset = ref<string | null>(null);
const renameValue = ref<string>("");
const renameError = ref<string | null>(null);

const deleteTarget = ref<string | null>(null);
const deleteError = ref<string | null>(null);
const panelMessage = ref<string | null>(null);

function busyState(name: string): BusyFlags {
  return store.datasetBusy[name] ?? {};
}

function statusLabel(name: string): string | null {
  const state = busyState(name);
  if (state.delete) return "Deleting…";
  if (state.rename) return "Renaming…";
  if (state.train) return "Training…";
  return null;
}

function durationLabel(seconds: number): string {
  if (!seconds) return "0s";
  if (seconds >= 3600) {
    return `${secondsFormatter.format(seconds / 3600)} h`;
  }
  if (seconds >= 60) {
    return `${secondsFormatter.format(seconds / 60)} min`;
  }
  return `${secondsFormatter.format(seconds)} s`;
}

function createdLabel(dataset: DatasetRecord): string {
  try {
    return createdFormatter.format(new Date(dataset.createdAt));
  } catch {
    return dataset.createdAt;
  }
}

function startRename(dataset: DatasetRecord): void {
  editingDataset.value = dataset.name;
  renameValue.value = dataset.name;
  renameError.value = null;
  deleteTarget.value = null;
  panelMessage.value = null;
}

function cancelRename(): void {
  editingDataset.value = null;
  renameValue.value = "";
  renameError.value = null;
}

async function submitRename(dataset: DatasetRecord): Promise<void> {
  const trimmed = renameValue.value.trim();
  if (!trimmed) {
    renameError.value = "Name cannot be empty.";
    return;
  }
  if (trimmed === dataset.name) {
    cancelRename();
    return;
  }
  try {
    await store.renameDataset(dataset.name, { name: trimmed });
    panelMessage.value = `Renamed dataset to ${trimmed}`;
    cancelRename();
  } catch (error) {
    renameError.value = parseErrorMessage(error);
  }
}

function requestDelete(dataset: DatasetRecord): void {
  deleteTarget.value = dataset.name;
  deleteError.value = null;
  editingDataset.value = null;
  panelMessage.value = null;
}

function cancelDelete(): void {
  deleteTarget.value = null;
  deleteError.value = null;
}

async function confirmDelete(dataset: DatasetRecord): Promise<void> {
  try {
    await store.deleteDataset(dataset.name);
    panelMessage.value = `Deleted dataset ${dataset.name}`;
    cancelDelete();
  } catch (error) {
    deleteError.value = parseErrorMessage(error);
    panelMessage.value = parseErrorMessage(error);
  }
}

async function triggerTrain(dataset: DatasetRecord): Promise<void> {
  panelMessage.value = null;
  try {
    await store.trainDataset(dataset.name);
    panelMessage.value = `Training job queued for ${dataset.name}`;
  } catch (error) {
    panelMessage.value = parseErrorMessage(error);
  }
}

function parseErrorMessage(error: unknown): string {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message ?? "Unknown error");
  }
  return "Unknown error";
}
</script>

<template>
  <section class="card dataset-panel">
    <header class="section-header">
      <div>
        <h2>Datasets</h2>
        <p class="subtitle">Manage corpora, trigger training, and keep class balance in view.</p>
      </div>
      <span class="badge" v-if="loading">Refreshing…</span>
    </header>

    <p v-if="panelMessage" class="panel-message">{{ panelMessage }}</p>

    <div v-if="datasets.length" class="dataset-grid">
      <article v-for="dataset in datasets" :key="dataset.name" class="dataset-card">
        <header class="dataset-card__header">
          <div class="dataset-card__title" v-if="editingDataset === dataset.name">
            <input
              v-model="renameValue"
              type="text"
              class="rename-input"
              maxlength="128"
              :disabled="busyState(dataset.name).rename"
              placeholder="Dataset name"
            />
            <div class="rename-actions">
              <button
                type="button"
                class="primary"
                :disabled="!renameValue.trim() || busyState(dataset.name).rename"
                @click="submitRename(dataset)"
              >
                {{ busyState(dataset.name).rename ? "Saving…" : "Save" }}
              </button>
              <button
                type="button"
                class="secondary"
                :disabled="busyState(dataset.name).rename"
                @click="cancelRename"
              >
                Cancel
              </button>
            </div>
            <p v-if="renameError" class="form-error">{{ renameError }}</p>
          </div>
          <template v-else>
            <h3>{{ dataset.name }}</h3>
            <p class="dataset-card__meta">
              Created {{ createdLabel(dataset) }} · {{ durationLabel(dataset.totalDurationSec) }}
            </p>
          </template>
          <span v-if="statusLabel(dataset.name)" class="badge status-badge">
            {{ statusLabel(dataset.name) }}
          </span>
        </header>

        <dl class="dataset-metrics">
          <div>
            <dt>Clips</dt>
            <dd>{{ formatter.format(dataset.clipCount) }}</dd>
          </div>
          <div>
            <dt>Positives</dt>
            <dd>{{ formatter.format(dataset.positives) }}</dd>
          </div>
          <div>
            <dt>Negatives</dt>
            <dd>{{ formatter.format(dataset.negatives) }}</dd>
          </div>
          <div>
            <dt>Noise</dt>
            <dd>{{ formatter.format(dataset.noise) }}</dd>
          </div>
          <div v-if="dataset.deletedClips">
            <dt>In trash</dt>
            <dd>{{ formatter.format(dataset.deletedClips ?? 0) }}</dd>
          </div>
        </dl>

        <div v-if="deleteTarget !== dataset.name && editingDataset !== dataset.name" class="dataset-card__actions">
          <button
            type="button"
            class="primary"
            :disabled="busyState(dataset.name).train"
            @click="triggerTrain(dataset)"
          >
            {{ busyState(dataset.name).train ? "Training…" : "Train model" }}
          </button>
          <button
            type="button"
            class="secondary"
            :disabled="busyState(dataset.name).rename"
            @click="startRename(dataset)"
          >
            Rename
          </button>
          <button
            type="button"
            class="ghost danger"
            :disabled="busyState(dataset.name).delete"
            @click="requestDelete(dataset)"
          >
            Delete
          </button>
        </div>

        <div v-if="deleteTarget === dataset.name" class="dataset-card__confirm">
          <p class="confirm-copy">This removes the dataset and all captured clips. This action cannot be undone.</p>
          <div class="confirm-actions">
            <button
              type="button"
              class="primary danger"
              :disabled="busyState(dataset.name).delete"
              @click="confirmDelete(dataset)"
            >
              {{ busyState(dataset.name).delete ? "Deleting…" : "Delete dataset" }}
            </button>
            <button
              type="button"
              class="secondary"
              :disabled="busyState(dataset.name).delete"
              @click="cancelDelete"
            >
              Cancel
            </button>
          </div>
          <p v-if="deleteError" class="form-error">{{ deleteError }}</p>
        </div>
      </article>
    </div>

    <p v-else class="empty-state">No datasets yet. Upload audio from the Pi to see activity.</p>
  </section>
</template>

<style scoped>
.dataset-panel {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

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

.panel-message {
  margin: 0;
  padding: 0.75rem 0.9rem;
  border-radius: 0.75rem;
  background: rgba(56, 189, 248, 0.18);
  border: 1px solid rgba(56, 189, 248, 0.35);
  color: #bae6fd;
  font-size: 0.9rem;
}

.dataset-grid {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.dataset-card {
  background: rgba(23, 37, 84, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 0.85rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: relative;
}

.dataset-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.dataset-card__title h3 {
  margin: 0;
  font-size: 1.35rem;
}

.dataset-card__meta {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  color: rgba(148, 163, 184, 0.75);
}

.status-badge {
  align-self: flex-start;
}

.dataset-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem;
}

.dataset-metrics div {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  padding: 0.65rem 0.75rem;
}

.dataset-metrics dt {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08rem;
  color: rgba(226, 232, 240, 0.6);
  margin: 0 0 0.25rem;
}

.dataset-metrics dd {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.dataset-card__actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.rename-input {
  width: 100%;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 0.7rem;
  padding: 0.55rem 0.75rem;
  color: inherit;
  font: inherit;
}

.rename-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.dataset-card__confirm {
  border: 1px dashed rgba(248, 113, 113, 0.45);
  border-radius: 0.75rem;
  padding: 0.85rem;
  background: rgba(127, 29, 29, 0.15);
  display: grid;
  gap: 0.75rem;
}

.confirm-copy {
  margin: 0;
  color: rgba(248, 250, 252, 0.85);
}

.confirm-actions {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
}

button.primary,
button.secondary,
button.ghost {
  border-radius: 999px;
  padding: 0.5rem 1.35rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
  transition: opacity 0.2s ease, transform 0.1s ease;
}

button.primary {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.35), rgba(59, 130, 246, 0.45));
  border: 1px solid rgba(37, 99, 235, 0.65);
  color: #f8fafc;
}

button.secondary {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.45);
  color: inherit;
}

button.ghost {
  background: transparent;
  border: 1px dashed rgba(148, 163, 184, 0.35);
  color: rgba(248, 250, 252, 0.85);
}

button.danger {
  border-color: rgba(248, 113, 113, 0.55);
  color: #fca5a5;
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.25), rgba(239, 68, 68, 0.35));
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

.form-error {
  margin: 0.35rem 0 0;
  color: #fca5a5;
  font-size: 0.85rem;
}

.empty-state {
  margin: 1.25rem 0 0;
  color: rgba(148, 163, 184, 0.75);
}

@media (max-width: 640px) {
  .dataset-card__actions {
    flex-direction: column;
  }
}
</style>
