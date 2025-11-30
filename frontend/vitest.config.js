import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/Components'),
      '@services': resolve(__dirname, 'src/services'),
      '@contexts': resolve(__dirname, 'src/contexts'),
      '@utils': resolve(__dirname, 'src/utils'),
    }
  }
})
