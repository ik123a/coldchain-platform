import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';

// Points at the already-running production build on :3000. The backend is on
// :8080 (NOT 8000 — another app holds that port) and is reached through the
// Next rewrite, so nothing here needs the backend address.
export default {
  targets: [
    {
      name: 'coldchain',
      engine: web({ viewport: { width: 1440, height: 900 } }),
      app: { url: process.env.APP_URL ?? 'http://127.0.0.1:3000' },
    },
  ],
  // Sequential: these tests register accounts and bind trucks in one shared
  // database, so parallel workers would race on the same rows.
  workers: 1,
} satisfies E2EConfig;