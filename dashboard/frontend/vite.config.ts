import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0', // Listen on all network interfaces for LAN access
    proxy: {
      '/api': {
        target: 'http://localhost:5203',
        changeOrigin: true,
      },
      '/graphql': {
        target: 'http://localhost:5203',
        changeOrigin: true,
      },
      '/hubs': {
        target: 'http://localhost:5203',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
