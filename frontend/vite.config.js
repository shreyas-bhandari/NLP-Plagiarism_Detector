import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Build output goes straight into the Flask backend so a single
// `python backend/app.py` serves both API and frontend in production.
export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname),
  build: {
    outDir: path.resolve(__dirname, '../backend/dist'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
