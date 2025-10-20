import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/ws': {
        target: 'ws://localhost:5000',
        ws: true,
        changeOrigin: true
      },
      '/api/config': {
        target: 'http://localhost:8081',
        changeOrigin: true
      },
      '/health': {
        target: 'http://localhost:8081',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    minify: 'esbuild',
    target: 'es2020',
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'pinia']
        }
      }
    }
  }
})
