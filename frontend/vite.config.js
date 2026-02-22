import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
  server: {
    proxy: {
      '/auth': 'http://localhost:8200',
      '/cal': 'http://localhost:8200',
      '/health': 'http://localhost:8200',
    },
  },
})
