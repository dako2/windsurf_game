import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['weight-shift-simulator-tunnel-ueevntbp.devinapps.com', 'weight-shift-simulator-tunnel-k48u98a8.devinapps.com', 'weight-shift-simulator-tunnel-trap41zf.devinapps.com', 'weight-shift-simulator-tunnel-udo24ci1.devinapps.com', 'localhost', '127.0.0.1']
  }
})
