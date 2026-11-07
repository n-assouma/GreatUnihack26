import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend (FastAPI) runs on :8000, see docs/CONTRACTS.md §1
const BACKEND = 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': BACKEND,
      '/static': BACKEND,
    },
  },
})
