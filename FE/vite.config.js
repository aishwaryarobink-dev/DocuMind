import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // This allows you to use @styles instead of ../styles
      '@styles': path.resolve(__dirname, './src/styles'),
    },
  },
  
 
})
