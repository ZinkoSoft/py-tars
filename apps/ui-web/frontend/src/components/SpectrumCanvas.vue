<template>
  <canvas ref="canvasRef" class="spectrum-canvas"></canvas>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Props {
  fftData?: number[]
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  fftData: () => [],
  width: 400,
  height: 120
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationFrameId: number | null = null

const drawSpectrum = () => {
  const canvas = canvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Set canvas size
  canvas.width = props.width
  canvas.height = props.height

  // Clear canvas
  ctx.fillStyle = '#0a0a12'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // If no FFT data, show baseline
  if (!props.fftData || props.fftData.length === 0) {
    ctx.strokeStyle = '#1e2545'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(0, canvas.height / 2)
    ctx.lineTo(canvas.width, canvas.height / 2)
    ctx.stroke()
    return
  }

  // Draw spectrum bars
  const barWidth = canvas.width / props.fftData.length
  const maxHeight = canvas.height * 0.8

  props.fftData.forEach((value, index) => {
    const barHeight = value * maxHeight
    const x = index * barWidth
    const y = canvas.height - barHeight

    // Create gradient for bar
    const gradient = ctx.createLinearGradient(x, y, x, canvas.height)
    gradient.addColorStop(0, '#5ac8fa')
    gradient.addColorStop(1, '#1d5682')

    ctx.fillStyle = gradient
    ctx.fillRect(x, y, barWidth - 1, barHeight)
  })
}

onMounted(() => {
  const animate = () => {
    drawSpectrum()
    animationFrameId = requestAnimationFrame(animate)
  }
  animate()
})

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }
})
</script>

<style scoped>
.spectrum-canvas {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 6px;
  background: var(--bg);
  border: 1px solid var(--border);
}
</style>
