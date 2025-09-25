<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useWakeTrainingStore, type DatasetRecord } from "@/stores/wakeTraining";

const props = defineProps<{
  datasets: DatasetRecord[];
  loading: boolean;
}>();

const store = useWakeTrainingStore();

const formatter = new Intl.NumberFormat();
const secondsFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 1,
});
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});

const editingDataset = ref<string | null>(null);
const renameValue = ref<string>("");
const renameError = ref<string | null>(null);
const confirmingDeletion = ref<string | null>(null);
const deleteErrors = ref<Record<string, string>>({});

const busyState = computed(() => store.datasetBusy);

watch(
  () => props.datasets.map((dataset) => dataset.name),
  (names) => {
    if (editingDataset.value && !names.includes(editingDataset.value)) {
      editingDataset.value = null;
      renameValue.value = "";
      renameError.value = null;
    }
    if (confirmingDeletion.value && !names.includes(confirmingDeletion.value)) {
      confirmingDeletion.value = null;
    }
    const nextErrors = { ...deleteErrors.value };
    let mutated = false;
    for (const key of Object.keys(nextErrors)) {
      if (!names.includes(key)) {
        delete nextErrors[key];
        mutated = true;
      }
    }
    if (mutated) {
      deleteErrors.value = nextErrors;
    }
  },
  { immediate: true },
);

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

function formattedDate(value: string): string {
  try {
    return dateFormatter.format(new Date(value));
  } catch {
    return value;
  }
}

function isBusy(name: string, key: "rename" | "delete" | "train"): boolean {
  return Boolean(busyState.value[name]?.[key]);
}

function startRename(dataset: DatasetRecord): void {
  editingDataset.value = dataset.name;
  renameValue.value = dataset.name;
  renameError.value = null;
  confirmingDeletion.value = null;
}

function cancelRename(): void {
  editingDataset.value = null;
  renameValue.value = "";
  renameError.value = null;
}

async function submitRename(originalName: string): Promise<void> {
  if (!editingDataset.value) {
    return;
  }
  if (!renameValue.value.trim()) {
    renameError.value = "Dataset name cannot be empty";
    return;
  }
  if (renameValue.value.trim() === originalName) {
    cancelRename();
    return;
  }

  try {
    await store.renameDataset(originalName, { name: renameValue.value.trim() });
    cancelRename();
  } catch (error) {
    renameError.value = parseError(error);
  }
}

function promptDelete(dataset: DatasetRecord): void {
  confirmingDeletion.value = dataset.name;
  deleteErrors.value = { ...deleteErrors.value, [dataset.name]: "" };
  editingDataset.value = null;
  renameError.value = null;
}

function cancelDelete(): void {
  if (confirmingDeletion.value) {
    const next = { ...deleteErrors.value };
    delete next[confirmingDeletion.value];
    deleteErrors.value = next;
  }
  confirmingDeletion.value = null;
}

async function performDelete(name: string): Promise<void> {
  try {
    await store.deleteDataset(name);
    cancelDelete();
  } catch (error) {
    deleteErrors.value = { ...deleteErrors.value, [name]: parseError(error) };
  }
}

async function queueTraining(dataset: DatasetRecord): Promise<void> {
  try {
    await store.trainDataset(dataset.name);
    if (deleteErrors.value[dataset.name]) {
      const next = { ...deleteErrors.value };
      delete next[dataset.name];
      deleteErrors.value = next;
    }
  } catch (error) {
    // Surface the error inline by storing it under deleteErrors map to avoid extra state
    deleteErrors.value = { ...deleteErrors.value, [dataset.name]: parseError(error) };
  }
}

function parseError(error: unknown): string {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message?: unknown }).message ?? "Unknown error");
  }
  return "Unknown error";
}

function classPercentage(value: number, total: number): string {
  if (!total) return "0%";
  return `${Math.round((value / total) * 100)}%`;
}
</script>

<template>
  <section class="card dataset-panel">
    <header class="section-header">
      <div>
        <h2>Datasets</h2>
        <p class="subtitle">Review totals, balance, and training actions per wake dataset.</p>
      </div>
      <span class="badge" v-if="loading">Refreshing…</span>
    </header>

    <p v-if="!datasets.length" class="empty-state">
      No datasets yet. Capture audio or upload samples to get started.
    </p>

    <div v-else class="dataset-grid">
      <article v-for="dataset in datasets" :key="dataset.name" class="dataset-card">
        <header class="dataset-card__header">
          <div>
            <h3>{{ dataset.name }}</h3>
            <p v-if="dataset.description" class="dataset-card__description">{{ dataset.description }}</p>
            <p v-else class="dataset-card__description placeholder">No description provided.</p>
          </div>
          <div class="dataset-card__actions">
            <button
              type="button"
              class="secondary"
              :disabled="isBusy(dataset.name, 'rename') || isBusy(dataset.name, 'delete')"
              @click="startRename(dataset)"
            >
              Rename
            </button>
            <button
              type="button"
              class="secondary danger"
              :disabled="isBusy(dataset.name, 'delete') || isBusy(dataset.name, 'rename')"
              @click="promptDelete(dataset)"
            >
              Delete
            </button>
            <button
              type="button"
              class="primary"
              :disabled="isBusy(dataset.name, 'train') || confirmingDeletion === dataset.name"
              @click="queueTraining(dataset)"
            >
              {{ isBusy(dataset.name, 'train') ? 'Queuing…' : 'Train' }}
            </button>
          </div>
        </header>

        <transition name="fade">
          <form
            v-if="editingDataset === dataset.name"
            class="rename-form"
            @submit.prevent="submitRename(dataset.name)"
          >
            <label class="field">
              <span>New name</span>
              <input
                v-model.trim="renameValue"
                type="text"
                :disabled="isBusy(dataset.name, 'rename')"
                placeholder="Wake dataset name"
              />
            </label>
            <div class="rename-actions">
              <button type="button" class="secondary" @click="cancelRename">Cancel</button>
              <button
                type="submit"
                class="primary"
                :disabled="isBusy(dataset.name, 'rename') || !renameValue.trim()"
              >
                {{ isBusy(dataset.name, 'rename') ? 'Saving…' : 'Save' }}
              </button>
            </div>
            <p class="error" v-if="renameError">{{ renameError }}</p>
          </form>
        </transition>

        <div class="dataset-card__metrics">
          <div class="metric">
            <span class="metric__label">Clips</span>
            <span class="metric__value">{{ formatter.format(dataset.clipCount) }}</span>
          </div>
          <div class="metric">
            <span class="metric__label">Total duration</span>
            <span class="metric__value">{{ durationLabel(dataset.totalDurationSec) }}</span>
          </div>
          <div class="metric">
            <span class="metric__label">Created</span>
            <span class="metric__value">{{ formattedDate(dataset.createdAt) }}</span>
          </div>
        </div>

        <div class="dataset-card__breakdown">
          <div>
            <span class="breakdown__label">Wake</span>
            <span class="breakdown__value">
              {{ formatter.format(dataset.positives) }}
              <small>{{ classPercentage(dataset.positives, dataset.clipCount) }}</small>
            </span>
          </div>
          <div>
            <span class="breakdown__label">Near miss</span>
            <span class="breakdown__value">
              {{ formatter.format(dataset.negatives) }}
              <small>{{ classPercentage(dataset.negatives, dataset.clipCount) }}</small>
            </span>
          </div>
          <div>
            <span class="breakdown__label">Noise</span>
            <span class="breakdown__value">
              {{ formatter.format(dataset.noise) }}
              <small>{{ classPercentage(dataset.noise, dataset.clipCount) }}</small>
            </span>
          </div>
        </div>

        <div
          class="dataset-card__delete"
          v-if="confirmingDeletion === dataset.name"
        >
          <p>Delete <strong>{{ dataset.name }}</strong>? This moves clips to trash and removes the dataset.</p>
          <div class="delete-actions">
            <button type="button" class="secondary" @click="cancelDelete">Cancel</button>
            <button
              type="button"
              class="primary danger"
              :disabled="isBusy(dataset.name, 'delete')"
              @click="performDelete(dataset.name)"
            >
              {{ isBusy(dataset.name, 'delete') ? 'Deleting…' : 'Delete' }}
            </button>
          </div>
          <p class="error" v-if="deleteErrors[dataset.name]">{{ deleteErrors[dataset.name] }}</p>
        </div>

        <p class="dataset-card__foot" v-else-if="dataset.deletedClips">
          {{ formatter.format(dataset.deletedClips) }} clips in trash.
        </p>
        <p class="dataset-card__foot" v-else>&nbsp;</p>

        <p class="error" v-if="deleteErrors[dataset.name] && confirmingDeletion !== dataset.name">
          {{ deleteErrors[dataset.name] }}
        </p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.dataset-panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
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

.empty-state {
  margin: 1.25rem 0 0;
  color: rgba(148, 163, 184, 0.75);
}

.dataset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.25rem;
}

.dataset-card {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 1rem;
  padding: 1.25rem;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.dataset-card__header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.dataset-card__header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.dataset-card__description {
  margin: 0.3rem 0 0;
  color: rgba(148, 163, 184, 0.8);
  font-size: 0.95rem;
}

.dataset-card__description.placeholder {
  font-style: italic;
  color: rgba(148, 163, 184, 0.55);
}

.dataset-card__actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

button.primary,
button.secondary {
  border-radius: 999px;
  padding: 0.45rem 1.1rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
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

button.secondary.danger,
.primary.danger {
  border-color: rgba(248, 113, 113, 0.65);
  color: #fca5a5;
}

.primary.danger {
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.3), rgba(239, 68, 68, 0.45));
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.rename-form {
  display: grid;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.85rem;
  background: rgba(15, 23, 42, 0.65);
  border: 1px dashed rgba(148, 163, 184, 0.35);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.95rem;
}

.field > span {
  font-weight: 600;
}

.field input {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 0.6rem;
  padding: 0.55rem 0.75rem;
  color: inherit;
  font: inherit;
}

.rename-actions {
  display: flex;
  gap: 0.75rem;
}

.dataset-card__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.75rem;
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.25);
}

.metric__label {
  font-size: 0.85rem;
  color: rgba(148, 163, 184, 0.75);
}

.metric__value {
  font-size: 1.15rem;
  font-weight: 600;
}

.dataset-card__breakdown {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.5rem;
}

.dataset-card__breakdown > div {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  padding: 0.6rem 0.85rem;
  background: rgba(15, 23, 42, 0.5);
}

.breakdown__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(148, 163, 184, 0.8);
}

.breakdown__value {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.1rem;
  font-weight: 600;
}

.breakdown__value small {
  font-size: 0.75rem;
  color: rgba(148, 163, 184, 0.65);
}

.dataset-card__delete {
  border: 1px solid rgba(248, 113, 113, 0.45);
  border-radius: 0.85rem;
  padding: 0.75rem;
  background: rgba(127, 29, 29, 0.2);
  display: grid;
  gap: 0.6rem;
}

.delete-actions {
  display: flex;
  gap: 0.75rem;
}

.dataset-card__foot {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(148, 163, 184, 0.75);
}

.error {
  margin: 0;
  color: #f87171;
  font-size: 0.85rem;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .dataset-card__actions {
    justify-content: flex-start;
  }
}
</style>
