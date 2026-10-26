import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/Three_slicer_responsive/',
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
  resolve: { dedupe: ['react', 'react-dom', 'three'] },
  worker: { format: 'es' },
  build: { target: 'es2022', sourcemap: true },
})
