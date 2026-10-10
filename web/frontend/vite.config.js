import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    chunkSizeWarningLimit: 600,
    rolldownOptions: {
      output: {
        advancedChunks: {
          groups: [
            {
              name: 'vendor-charts',
              test: /node_modules[\\/](recharts|d3-[a-z-]+|victory-vendor)/,
            },
            {
              name: 'vendor-map',
              test: /node_modules[\\/](leaflet|react-leaflet|@react-leaflet)/,
            },
            {
              name: 'vendor-motion',
              test: /node_modules[\\/](gsap|@gsap)/,
            },
            {
              name: 'vendor-react',
              test: /node_modules[\\/](react|react-dom|react-router|scheduler)/,
            },
          ],
        },
      },
    },
  },
})
