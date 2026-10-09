import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard is served by the API under /admin, so assets need that base path.
export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
})
