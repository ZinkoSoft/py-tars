<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, shallowRef } from "vue";
import { AudioRecorder, type AudioRecording } from "@/lib/audioRecorder";
import type { DatasetRecord } from "@/stores/wakeTraining";
import { useWakeTrainingStore } from "@/stores/wakeTraining";

const props = defineProps<{
  datasets: DatasetRecord[];
  loading: boolean;
}>();

const store = useWakeTrainingStore();

type PanelPhase = "idle" | "countdown" | "recording" | "review" | "uploading" | "error";

const selectedDataset = ref<string>("");
const label = ref<"positive" | "negative" | "noise">("positive");
const speaker = ref<string>("");
const notes = ref<string>("");

const phase = ref<PanelPhase>("idle");
const countdown = ref<number>(3);
const level = ref<number>(0);
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const recording = ref<AudioRecording | null>(null);
const recordingStartedAt = ref<number | null>(null);
const elapsedSeconds = ref<number>(0);

const recorder = shallowRef<AudioRecorder | null>(null);
let countdownTimer: number | null = null;
let elapsedTimer: number | null = null;

const datasetNames = computed(() => props.datasets.map((dataset) => dataset.name));

watch(
  () => datasetNames.value,
  (names) => {
    if (!selectedDataset.value && names.length > 0) {
      selectedDataset.value = names[0];
    }
    if (selectedDataset.value && names.length > 0 && !names.includes(selectedDataset.value)) {
      selectedDataset.value = names[0];
    }
    if (names.length === 0) {
      selectedDataset.value = "";
    }
  },
  { immediate: true },
);

const canStart = computed(() => {
  if (!selectedDataset.value) return false;
  return phase.value === "idle" || phase.value === "review" || phase.value === "error";
});

const showLevel = computed(() => phase.value === "recording");
const levelPercent = computed(() => Math.min(100, Math.round(level.value * 100)));

const formattedElapsed = computed(() => {
  if (phase.value !== "recording" || elapsedSeconds.value <= 0) {
    return "0.0";
  }
  return elapsedSeconds.value.toFixed(1);
});

function ensureRecorder(): AudioRecorder {
  if (!recorder.value) {
    recorder.value = new AudioRecorder({
      onLevel: (value) => {
        level.value = value;
      },
    });
  }
  return recorder.value;
}

async function beginRecording(): Promise<void> {
  if (!selectedDataset.value) {
    errorMessage.value = "Select a dataset before recording.";
    phase.value = "error";
    return;
  }

  successMessage.value = null;
  errorMessage.value = null;
  phase.value = "idle";

  try {
    const rec = ensureRecorder();
    await rec.init();
    startCountdown();
  } catch (error) {
    handleError(error);
  }
}

function startCountdown(): void {
  clearCountdown();
  countdown.value = 3;
  phase.value = "countdown";
  countdownTimer = window.setInterval(async () => {
    if (countdown.value > 1) {
      countdown.value -= 1;
      return;
    }
    clearCountdown();
    try {
      const rec = ensureRecorder();
      await rec.start();
      phase.value = "recording";
      recordingStartedAt.value = performance.now();
      startElapsedTimer();
    } catch (error) {
      handleError(error);
    }
  }, 1000);
}

async function stopRecording(): Promise<void> {
  if (!recorder.value || phase.value !== "recording") {
    return;
  }

  try {
    const result = await recorder.value.stop();
    stopElapsedTimer();
    recording.value = result;
    phase.value = "review";
    level.value = 0;
    elapsedSeconds.value = result.duration;
  } catch (error) {
    handleError(error);
  }
}

function retake(): void {
  if (recording.value) {
    URL.revokeObjectURL(recording.value.url);
  }
  recording.value = null;
  elapsedSeconds.value = 0;
  phase.value = "idle";
  errorMessage.value = null;
}

async function uploadClip(): Promise<void> {
  if (!recording.value || !selectedDataset.value) {
    return;
  }

  phase.value = "uploading";
  errorMessage.value = null;
  successMessage.value = null;

  try {
    await store.uploadRecording(selectedDataset.value, recording.value.blob, {
      label: label.value,
      speaker: speaker.value || undefined,
      notes: notes.value || undefined,
    });
    successMessage.value = `Uploaded clip to ${selectedDataset.value}`;
    if (recording.value) {
      URL.revokeObjectURL(recording.value.url);
    }
    recording.value = null;
    elapsedSeconds.value = 0;
    notes.value = "";
    phase.value = "idle";
  } catch (error) {
    handleError(error);
    phase.value = "review";
  }
}

function startElapsedTimer(): void {
  stopElapsedTimer();
  elapsedSeconds.value = 0;
  elapsedTimer = window.setInterval(() => {
    if (recordingStartedAt.value === null) {
      elapsedSeconds.value = 0;
      return;
    }
    const now = performance.now();
    elapsedSeconds.value = (now - recordingStartedAt.value) / 1000;
  }, 100);
}

function stopElapsedTimer(): void {
  if (elapsedTimer !== null) {
    window.clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
  recordingStartedAt.value = null;
}

function clearCountdown(): void {
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function handleError(error: unknown): void {
  stopElapsedTimer();
  clearCountdown();
  const message = error instanceof Error ? error.message : "Unable to access microphone.";
  errorMessage.value = message;
  phase.value = "error";
}

const uploadDisabled = computed(() => {
  if (!recording.value || store.uploadingRecording) {
    return true;
  }
  return !selectedDataset.value;
});

onBeforeUnmount(() => {
  clearCountdown();
  stopElapsedTimer();
  recorder.value?.dispose();
  if (recording.value) {
    URL.revokeObjectURL(recording.value.url);
  }
});
</script>

<template>
  <section class="card recorder">
    <header class="section-header">
      <div>
        <h2>Capture new audio</h2>
        <p class="subtitle">Guided countdown, real-time levels, and upload automation for wake datasets.</p>
      </div>
      <span class="badge" v-if="store.uploadingRecording">Uploading…</span>
      <span class="badge success" v-else-if="successMessage">{{ successMessage }}</span>
    </header>

    <div class="form-grid">
      <label class="field">
        <span>Dataset</span>
        <select v-model="selectedDataset" :disabled="!datasetNames.length || store.uploadingRecording || props.loading">
          <option value="" disabled>Select a dataset</option>
          <option v-for="name in datasetNames" :key="name" :value="name">
            {{ name }}
          </option>
        </select>
      </label>

      <fieldset class="field">
        <legend>Label</legend>
        <div class="label-group">
          <button type="button" :class="['label-pill', { active: label === 'positive' }]" @click="label = 'positive'">
            Wake word
          </button>
          <button type="button" :class="['label-pill', { active: label === 'negative' }]" @click="label = 'negative'">
            Near miss
          </button>
          <button type="button" :class="['label-pill', { active: label === 'noise' }]" @click="label = 'noise'">
            Noise
          </button>
        </div>
      </fieldset>

      <label class="field">
        <span>Speaker tag</span>
        <input v-model="speaker" type="text" placeholder="Optional identifier" :disabled="store.uploadingRecording" />
      </label>
    </div>

    <label class="field notes">
      <span>Notes</span>
      <textarea v-model="notes" rows="3" placeholder="Mic distance, background context, or session metadata" :disabled="store.uploadingRecording" />
    </label>

    <div class="recorder-stage">
      <div class="stage-indicator" :class="phase">
        <template v-if="phase === 'idle'">
          <p class="stage-title">Ready to record</p>
          <p class="stage-subtitle">Press start, wait for the 3-count, then speak the wake phrase clearly.</p>
          <button class="primary" type="button" :disabled="!canStart" @click="beginRecording">
            Start countdown
          </button>
        </template>

        <template v-else-if="phase === 'countdown'">
          <p class="stage-title">Starting in</p>
          <p class="countdown-display">{{ countdown }}</p>
          <p class="stage-subtitle">Get in position – recording begins when the countdown ends.</p>
        </template>

        <template v-else-if="phase === 'recording'">
          <p class="stage-title recording">Recording</p>
          <p class="stage-subtitle">Speak now. Clip length: {{ formattedElapsed }}s</p>
          <div class="meter" v-if="showLevel">
            <div class="meter-fill" :style="{ width: `${levelPercent}%` }"></div>
          </div>
          <button class="primary danger" type="button" @click="stopRecording">Stop</button>
        </template>

        <template v-else-if="phase === 'review' && recording">
          <p class="stage-title">Review clip</p>
          <p class="stage-subtitle">Duration: {{ recording.duration.toFixed(1) }}s @ {{ recording.sampleRate }} Hz</p>
          <audio :src="recording.url" controls preload="metadata"></audio>
          <div class="actions">
            <button type="button" class="secondary" @click="retake">Retake</button>
            <button type="button" class="primary" :disabled="uploadDisabled" @click="uploadClip">Upload clip</button>
          </div>
        </template>

        <template v-else-if="phase === 'uploading'">
          <p class="stage-title">Uploading…</p>
          <p class="stage-subtitle">Sending audio to the wake training API.</p>
        </template>

        <template v-else-if="phase === 'error'">
          <p class="stage-title">Recording unavailable</p>
          <p class="stage-subtitle">{{ errorMessage ?? 'Microphone access was denied or interrupted.' }}</p>
          <button class="secondary" type="button" :disabled="store.uploadingRecording" @click="beginRecording">
            Try again
          </button>
        </template>
      </div>
    </div>

    <p class="error" v-if="errorMessage">{{ errorMessage }}</p>
    <p class="error" v-else-if="store.lastUploadError">{{ store.lastUploadError }}</p>
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

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin: 1.25rem 0 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.95rem;
}

.field > span,
.field legend {
  font-weight: 600;
}

.field select,
.field input,
.field textarea {
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 0.6rem;
  padding: 0.55rem 0.75rem;
  color: inherit;
  font: inherit;
}

.field textarea {
  resize: vertical;
}

.label-group {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.label-pill {
  padding: 0.45rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.label-pill.active {
  background: rgba(56, 189, 248, 0.25);
  border-color: rgba(56, 189, 248, 0.8);
  color: #38bdf8;
}

.recorder-stage {
  margin: 1.5rem 0 0.75rem;
}

.stage-indicator {
  border: 1px dashed rgba(148, 163, 184, 0.4);
  border-radius: 1rem;
  padding: 1.5rem;
  display: grid;
  gap: 0.75rem;
  justify-items: center;
  text-align: center;
}

.stage-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
}

.stage-title.recording {
  color: #f97316;
}

.stage-subtitle {
  margin: 0;
  color: rgba(148, 163, 184, 0.8);
}

.countdown-display {
  font-size: 3.75rem;
  font-weight: 700;
  margin: 0.25rem 0 0.35rem;
  letter-spacing: 0.15rem;
}

.meter {
  width: 100%;
  max-width: 360px;
  height: 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.25);
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  background: linear-gradient(90deg, #34d399, #fbbf24, #f87171);
  transition: width 0.15s ease;
}

.actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

button.primary,
button.secondary {
  border-radius: 999px;
  padding: 0.5rem 1.35rem;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
}

button.primary {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.35), rgba(59, 130, 246, 0.45));
  border: 1px solid rgba(37, 99, 235, 0.65);
  color: #f8fafc;
}

button.primary.danger {
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.35), rgba(239, 68, 68, 0.45));
  border-color: rgba(248, 113, 113, 0.75);
}

button.secondary {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.45);
  color: inherit;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.stage-indicator audio {
  width: 100%;
}

.error {
  margin: 0.5rem 0 0;
  color: #f87171;
}

.badge.success {
  background: rgba(96, 165, 250, 0.2);
  color: #93c5fd;
  border-color: rgba(147, 197, 253, 0.35);
}

@media (max-width: 640px) {
  .stage-indicator {
    padding: 1.25rem;
  }
}
</style>
