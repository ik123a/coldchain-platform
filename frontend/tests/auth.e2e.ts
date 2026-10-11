import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

// No model is used anywhere in this file: every assertion is a locator check, so
// the suite runs deterministically with no API key.
//
// Each test creates its OWN account. An earlier version registered once and let
// later tests depend on that session, which made them order-dependent — they
// passed or failed based on file ordering rather than on the app's behaviour.

function acct(tag: string) {
  const s = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  return { tag, email: `e2e_${tag}_${s}@coldchain.io`, password: 'secret123' };
}

async function registerOperator(app: any, screen: any, a: ReturnType<typeof acct>) {
  await app.open('/login');
  // The mode switch is a tablist (role=tab), disambiguating it from the submit
  // button — both carry the accessible name "Create account". The role toggle
  // below it is a plain button pair, so it uses role=button.
  await screen.getByRole('tab', 'Create account').tap();
  await screen.getByRole('button', 'Operator').tap();
  await screen.getByLabel('Name').fill('E2E Operator');
  await screen.getByLabel('Email').fill(a.email);
  await screen.getByLabel('Password').fill(a.password);
  await screen.getByRole('button', 'Create account & sign in').tap();
}

test('an unauthenticated visitor is sent to the login page', async ({ app, screen, browser }) => {
  await app.open('/dashboard');
  await expect(browser).toHaveURL('/login');
  // The submit button, not the tab — the tablist uses role=tab.
  await expect(screen.getByRole('button', 'Sign in')).toBeVisible();
});

test('a new operator registers and lands on the dashboard', async ({ app, screen, browser }) => {
  const a = acct('reg');
  await registerOperator(app, screen, a);

  await expect(browser).toHaveURL('/dashboard');
  // The signed-in identity must be visible in the shell, not merely implied.
  await expect(screen.getByText('E2E Operator')).toBeVisible();
  await expect(screen.getByRole('link', 'Live Map')).toBeVisible();
});

test('the operator shell reaches the backend and reports 14 twins', async ({ app, screen, browser }) => {
  const a = acct('shell');
  await registerOperator(app, screen, a);
  await expect(browser).toHaveURL('/dashboard');

  // This is the regression that broke silently before: a stale API_ORIGIN left
  // every /api call 404ing while the page still rendered a plausible shell.
  //
  // Located by CSS, not accessible name: the row's label is uppercased by CSS
  // ("DATABASE Connected") while the snapshot reports it title-cased, so a
  // name-based match is brittle. getByText("Connected") is worse — it is
  // ambiguous, the word also appears in the header badge.
  const dbRow = browser.locator('aside li:has-text("Connected")');
  await expect(dbRow).toBeVisible({ timeout: 20_000 });
  await expect(dbRow).toContainText(/database/i);
  await expect(screen.getByText('14 twins')).toBeVisible({ timeout: 20_000 });
});

test('bad credentials surface an error and do not sign in', async ({ app, screen, browser }) => {
  const a = acct('bad');
  // Register so the account definitely exists, sign out, then try bad creds.
  await registerOperator(app, screen, a);
  await expect(browser).toHaveURL('/dashboard');
  await screen.getByRole('button', 'Sign out').tap();
  await expect(browser).toHaveURL('/login');

  await screen.getByLabel('Email').fill(a.email);
  await screen.getByLabel('Password').fill('wrong-password');
  await screen.getByRole('button', 'Sign in').tap();

  await expect(screen.getByText('Invalid email or password.')).toBeVisible();
  await expect(browser).toHaveURL('/login');
});

test('signing out clears the session and re-guards the app', async ({ app, screen, browser }) => {
  const a = acct('out');
  await registerOperator(app, screen, a);
  await expect(browser).toHaveURL('/dashboard');

  await screen.getByRole('button', 'Sign out').tap();
  await expect(browser).toHaveURL('/login');

  // The guard must hold AFTER logout, not just during it.
  await app.open('/dashboard');
  await expect(browser).toHaveURL('/login');
  await expect(screen.getByLabel('Password')).toBeVisible();
});