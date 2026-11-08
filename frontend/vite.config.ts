import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
    // public/replays/ holds local model replays (model/export_dashboard.py) for `?replay=` links in dev.
    // They are big and made on this computer only, so they never go into dist/ (or onto the Pi).
    {
      name: 'drop-local-replays',
      apply: 'build',
      closeBundle() {
        rmSync(fileURLToPath(new URL('./dist/replays', import.meta.url)), { recursive: true, force: true });
      },
    },
  ],
  // --host in package.json exposes the dev server on the LAN (phone / tablet on the same Wi-Fi).
  server: { port: 5173 },
});
