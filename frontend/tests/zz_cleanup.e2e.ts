import { test, expect, ACCOUNT_PREFIXES } from './_helpers';

// Runs LAST (the file name sorts after auth/driver, and the runner uses one
// sequential worker). It restores the state the suite touched:
//   1. deletes the throwaway accounts this suite created — which releases their
//      truck claims, the thing that breaks a later run with "no free truck"
//   2. restarts the fleet so injected faults, positions and events do not leak
//      into the next run or a demo
//
// Scoped by email prefix, never a blanket delete: a real operator's account is
// not matched by `e2e_`/`drv_`. No time cutoff either, so a run that crashed
// before its own cleanup is healed by the next one.
//
// AUTHENTICATION. The backend is now fail-closed: mutating routes require a
// bearer token even in development (previously APP_ENV=development silently made
// them anonymous). Cleanup therefore signs in first and sends the token. This is
// the correct direction — the suite authenticates like any other client rather
// than the server being left open to keep the suite green.
test('test suite cleanup: release accounts and restart the fleet', async () => {
  // Sign in with an operator account the suite is allowed to use.
  const email = process.env.E2E_OPERATOR_EMAIL || 'ops@test.local';
  const password = process.env.E2E_OPERATOR_PASSWORD || 'secret123';

  const loginRes = await fetch('http://127.0.0.1:8080/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!loginRes.ok) {
    const body = await loginRes.text().catch(() => '');
    throw new Error(
      `cleanup could not authenticate as ${email} (HTTP ${loginRes.status}). ` +
        `Set E2E_OPERATOR_EMAIL / E2E_OPERATOR_PASSWORD to an operator account. ${body.slice(0, 160)}`,
    );
  }
  const { access_token } = await loginRes.json();

  const res = await fetch('http://127.0.0.1:8080/api/fleet/maintenance/cleanup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${access_token}`,
    },
    body: JSON.stringify({
      prefixes: ACCOUNT_PREFIXES,
      restart_fleet: true,
    }),
  });

  // The endpoint is real infrastructure now, so a failure is a failure — this
  // assertion can go red. Silently skipping cleanup is what left the fleet
  // claimed in the first place.
  expect(res.ok, `cleanup endpoint returned ${res.status}`).toBeTruthy();
  const out = await res.json();
  console.log(
    `[cleanup] removed ${out.accounts_deleted} test accounts, ` +
      `released ${out.trucks_released} trucks, fleet restarted: ${out.fleet_restarted}`,
  );
});
