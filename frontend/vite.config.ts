import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['weight-shift-simulator-tunnel-pao7glw2.devinapps.com', 'localhost', '127.0.0.1']
  }
})
