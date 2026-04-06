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
        // Chunk splitting avoids one massive JS file hitting the browser at once
        manualChunks: {
          'react-core': ['react', 'react-dom', 'react-router-dom'],
          'ui-tools': ['framer-motion', 'lucide-react', 'clsx', 'tailwind-merge'],
          'code-editor': ['@monaco-editor/react'],
          'charts': ['d3', 'recharts'],
          'markdown': ['react-markdown', 'remark-gfm'],
        },
      },
    },
    chunkSizeWarningLimit: 1000, // Increased limit due to heavy viz libraries
  },
})
