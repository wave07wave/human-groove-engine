import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { output: { manualChunks: { audio: ['tone'] } } },
  },
  test: { environment: 'jsdom', globals: true, maxWorkers: 2 },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' },
  },
})
