/**
 * Spectrum Store
 *
 * Manages audio spectrum (FFT) data for visualization.
 *
 * @module stores/spectrum
 */

import { defineStore } from 'pinia'
import { ref, type Ref } from 'vue'
import type { AudioFFTMessage } from '../types/mqtt'

export const useSpectrumStore = defineStore('spectrum', () => {
  // State
  const currentFFT: Ref<number[]> = ref([])
  const lastUpdate: Ref<number | null> = ref(null)
  const sampleRate: Ref<number | null> = ref(null)

  // Actions
  function updateFFT(message: AudioFFTMessage): void {
    currentFFT.value = [...message.fft]
    lastUpdate.value = message.timestamp || Date.now()
    if (message.sample_rate) {
      sampleRate.value = message.sample_rate
    }
  }

  function clearFFT(): void {
    currentFFT.value = []
    lastUpdate.value = null
  }

  return {
    // State
    currentFFT,
    lastUpdate,
    sampleRate,

    // Actions
    updateFFT,
    clearFFT
  }
})
