import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

// Each test registers its OWN driver, so no test depends on another's session.
// An earlier version shared one account across three tests, which made results
// depend on file ordering.
function acct() {
  const s = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  return { email: `drv_${s}@coldchain.io`, password: 'secret123' };
}

async function registerDriver(app: any, screen: any, browser: any, a: ReturnType<typeof acct>) {
  await app.open('/login');
  // role 'tab' (mode switch) vs role 'button' (submit) — both named
  // "Create account" before the tablist fix.
  await screen.getByRole('tab', 'Create account').tap();
  await screen.getByRole('button', 'Truck driver').tap();
  await screen.getByLabel('Name').fill('E2E Driver');
  await screen.getByLabel('Email').fill(a.email);
  await screen.getByLabel('Password').fill(a.password);
  await screen.getByRole('button', 'Create account & sign in').tap();
  // A driver must never land on the operator dashboard.
  await expect(browser).toHaveURL('/driver');
}

test('a driver registers, claims a free truck and sees only that truck', async ({
  app,
  screen,
  browser,
}) => {
  await registerDriver(app, screen, browser, acct());

  // First run picks a truck; the picker lists real fleet ids.
  await expect(screen.getByText('Which truck do you drive?')).toBeVisible();
  await screen.getByRole('button', { name: /assign/ }).first().tap();

  // Own-truck console: the metrics the driver is accountable for.
  await expect(screen.getByText('DRIVER CONSOLE')).toBeVisible();
  await expect(screen.getByText('Cargo temp')).toBeVisible();
  await expect(screen.getByText('Speed')).toBeVisible();
  await expect(screen.getByText('Safe band')).toBeVisible();

  // The predictive verdict must be shown WITH its honesty caveat — the model is
  // a linear trend projection, and that must travel with the number.
  await expect(screen.getByText('Margin to limit')).toBeVisible({ timeout: 20_000 });
  await expect(screen.getByText(/linear trend projection/i)).toBeVisible({ timeout: 20_000 });
});

test('a driver is blocked from the operator dashboard', async ({ app, screen, browser }) => {
  await registerDriver(app, screen, browser, acct());
  await screen.getByRole('button', { name: /assign/ }).first().tap();
  await expect(screen.getByText('DRIVER CONSOLE')).toBeVisible();

  // The RBAC guard: a driver requesting an operator route is bounced back.
  await app.open('/dashboard');
  await expect(browser).toHaveURL('/driver');
  await expect(screen.getByText('DRIVER CONSOLE')).toBeVisible();
});

test('a driver can release their truck and pick another', async ({ app, screen, browser }) => {
  await registerDriver(app, screen, browser, acct());
  await screen.getByRole('button', { name: /assign/ }).first().tap();
  await expect(screen.getByText('DRIVER CONSOLE')).toBeVisible();

  await screen.getByText('change truck').tap();
  await expect(screen.getByText('Which truck do you drive?')).toBeVisible();

  await screen.getByRole('button', { name: /assign/ }).first().tap();
  await expect(screen.getByText('Cargo temp')).toBeVisible({ timeout: 20_000 });
});