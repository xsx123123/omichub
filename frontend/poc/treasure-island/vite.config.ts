import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'
export default defineConfig({
  root: __dirname, plugins: [vue()], envDir: '/tmp/treasure-island-no-env',
  resolve: { alias: { '@treasure-island-poc': resolve(__dirname, '../../public/treasure-island/treasure-island.js') } },
  server: { host: '127.0.0.1', port: 5178, strictPort: true, fs: { allow: [resolve(__dirname, '../../..')] } },
  build: { outDir: '/tmp/treasure-vue-poc-dist', emptyOutDir: true },
})
