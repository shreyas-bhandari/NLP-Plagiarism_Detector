import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to the Flask backend so the browser only ever talks
// to one origin. In production Flask serves the built files from ./dist.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // The dev server may be reached through a proxied host (containers, tunnels,
    // hosted previews). Vite's host allow-list would reject those requests, so the
    // dev server is opened to any hostname. This affects `npm run dev` only; in
    // production Flask serves the built bundle and no dev server runs.
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
})
