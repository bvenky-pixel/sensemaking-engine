import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Dev proxy forwards API calls to the real uvicorn server (see
// frontend/decisions.md "Build the real Confidant frontend") -- this
// project never develops against a mock backend. Run
// `uvicorn src.api.server:app --reload` separately, then `npm run dev`.
export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/sessions': 'http://127.0.0.1:8000',
    },
  },
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.js'],
  },
})
