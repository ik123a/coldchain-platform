import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

// Shared helpers for the suite.
//
// CLEANUP IS NOT HERE ON PURPOSE.
// An `afterAll` in this module fires per-FILE, so it ran after auth.e2e.ts and
// the driver file's accounts survived (measured: 3 accounts / 3 trucks still held
// after a "clean" run). Cleanup lives in zz_cleanup.e2e.ts, which the runner
// orders last, so it covers every account the run created.

// Timestamp-derived email that is also easy to identify after the fact.
export function acct(tag = 't') {
  const s = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  return {
    tag,
    email: `e2e_${tag}_${s}@coldchain.io`,
    password: 'secret123',
  };
}

// The suite's email prefixes. Cleanup only removes rows matching one of these.
export const ACCOUNT_PREFIXES = ['e2e_', 'drv_'];

// Re-export so test files import everything from one place.
export { test, expect };
