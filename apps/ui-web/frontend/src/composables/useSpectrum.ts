import { ref, watch, onUnmounted } from 'vue'

export interface SpectrumData {
  fft: number[]
  timestamp?: number
}

export function useSpectrum(isDrawerOpen: () => boolean) {
  const fftData = ref<number[]>([])
  const lastUpdateTime = ref<number>(0)
  const fadeTimeout = ref<number | null>(null)

  // Fade to baseline when no data for 2 seconds
  const FADE_DELAY = 2000

  const updateFFTData = (data: SpectrumData) => {
    if (!isDrawerOpen()) return

    fftData.value = [...data.fft]
    lastUpdateTime.value = Date.now()

    // Clear existing fade timeout
    if (fadeTimeout.value !== null) {
      clearTimeout(fadeTimeout.value)
      fadeTimeout.value = null
    }

    // Set new fade timeout
    fadeTimeout.value = window.setTimeout(() => {
      fftData.value = []
    }, FADE_DELAY)
  }

  const clearFFTData = () => {
    fftData.value = []
    if (fadeTimeout.value !== null) {
      clearTimeout(fadeTimeout.value)
      fadeTimeout.value = null
    }
  }

  // Pause rendering when drawer is closed
  watch(isDrawerOpen, open => {
    if (!open) {
      clearFFTData()
    }
  })

  onUnmounted(() => {
    if (fadeTimeout.value !== null) {
      clearTimeout(fadeTimeout.value)
    }
  })

  return {
    fftData,
    updateFFTData,
    clearFFTData
  }
}
