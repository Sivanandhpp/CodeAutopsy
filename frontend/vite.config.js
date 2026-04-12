import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // ─── PRODUCTION OPTIMIZATIONS ──────────────────────────────────────
    target: 'esnext',
    minify: 'terser', 
    cssMinify: true,
    terserOptions: {
      compress: {
        drop_console: true, // Removes console logs in production
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts', 'd3'],
          editor: ['@monaco-editor/react'],
          motion: ['framer-motion'],
        },
      },
    },
    chunkSizeWarningLimit: 1000, // Increased limit due to heavy viz libraries
  },
})
