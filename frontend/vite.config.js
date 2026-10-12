import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      // 开发时前端直接调 /api/*，由 Vite 转发到 FastAPI，避免跨域
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 900,
  },
})
