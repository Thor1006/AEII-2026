import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // --host in package.json exposes the dev server on the LAN (phone / tablet on the same Wi-Fi).
  server: { port: 5173 },
});
