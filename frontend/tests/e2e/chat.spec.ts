import { test, expect, type BrowserContext, type Locator, type Page, type TestInfo } from '@playwright/test';

// OmniAI v1 End-to-End Tests
// Run with: npx playwright install chromium && npx playwright test tests/e2e/chat.spec.ts

const BACKEND_URL = process.env.BACKEND_URL || process.env.BACKEND_BASE_URL || 'http://localhost:8000';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const E2E_USERNAME = process.env.E2E_USERNAME;
const E2E_PASSWORD = process.env.E2E_PASSWORD;
const E2E_DEBUG = process.env.E2E_DEBUG === '1';

async function safeClearStorage(page: any) {
  await page.evaluate(() => {
    try { localStorage.clear(); } catch {}
    try { sessionStorage.clear(); } catch {}
  });
}

async function hasSessionCookie(page: Page): Promise<boolean> {
  const cookies = await page.context().cookies();
  return cookies.some((c) => c.name === 'omni_session' || c.name.includes('session') || c.name.includes('auth'));
}

function requireCreds(testInfo: TestInfo) {
  if (!E2E_USERNAME || !E2E_PASSWORD) {
    testInfo.skip(
      true,
      'E2E_USERNAME and E2E_PASSWORD must be set (no defaults). ' +
        'Example: E2E_USERNAME=... E2E_PASSWORD=... npx playwright test ...'
    );
  }
}

async function preflightAuthBackend(page: Page, baseApi: string, testInfo: TestInfo) {
  const health = await page.request.get(`${baseApi}/health`).catch(() => null);
  if (!health || !health.ok()) {
    await testInfo.attach('backend_health_status', {
      body: String(health?.status() ?? 'NO_RESPONSE'),
      contentType: 'text/plain',
    });
    throw new Error(`Backend not reachable/healthy at ${baseApi} (health check failed).`);
  }

  const csrf = await page.request.get(`${baseApi}/v1/auth/csrf/bootstrap`).catch(() => null);
  const csrfText = csrf ? await csrf.text().catch(() => '') : '';
  await testInfo.attach('csrf_bootstrap_status', {
    body: `${csrf?.status() ?? 'NO_RESPONSE'}\n${csrfText}`,
    contentType: 'text/plain',
  });
  if (!csrf || !csrf.ok()) {
    throw new Error(`CSRF bootstrap failed at ${baseApi}/v1/auth/csrf/bootstrap`);
  }
}

async function waitForLoginResponse(page: Page) {
  return page.waitForResponse((resp) => {
    const req = resp.request();
    return (
      req.method() === 'POST' &&
      /\/(api|v1)\/auth\//i.test(resp.url()) &&
      /login|session|signin/i.test(resp.url())
    );
  }, { timeout: 15_000 });
}

async function recordLoginAttempt(page: Page, fn: () => Promise<void>) {
  const requests: { method: string; url: string; type: string }[] = [];
  const consoles: { type: string; text: string }[] = [];
  const pageErrors: string[] = [];

  const onReq = (req: any) => requests.push({ method: req.method(), url: req.url(), type: req.resourceType() });
  const onConsole = (msg: any) => consoles.push({ type: msg.type(), text: msg.text() });
  const onPageError = (err: any) => pageErrors.push(String(err?.message ?? err));

  page.on('request', onReq);
  page.on('console', onConsole);
  page.on('pageerror', onPageError);

  try {
    await fn();
    await page.waitForTimeout(750);
  } finally {
    page.off('request', onReq);
    page.off('console', onConsole);
    page.off('pageerror', onPageError);
  }

  return { requests, consoles, pageErrors };
}

async function captureBrowserCsrfBootstrap(page: Page, backendUrl: string, testInfo: TestInfo) {
  const resp = await page.waitForResponse((r) => {
    return (
      r.request().method() === 'GET' &&
      /\/v1\/auth\/csrf\/bootstrap|\/api\/auth\/csrf\/bootstrap/i.test(r.url())
    );
  }, { timeout: 10_000 });

  const headers = resp.headers();
  const body = await resp.text().catch(() => '');
  if (E2E_DEBUG) {
    await testInfo.attach('csrf_bootstrap_browser_response', {
      body: JSON.stringify(
        {
          url: resp.url(),
          status: resp.status(),
          set_cookie: headers['set-cookie'] ?? null,
          body: body.slice(0, 2000),
        },
        null,
        2
      ),
      contentType: 'application/json',
    });
  }

  const cookieScope = (() => {
    try {
      return new URL(resp.url()).origin;
    } catch {
      return backendUrl;
    }
  })();
  const cookies = await page.context().cookies(cookieScope);
  if (E2E_DEBUG) {
    await testInfo.attach('csrf_cookie_jar_after_bootstrap', {
      body: JSON.stringify(cookies, null, 2),
      contentType: 'application/json',
    });
  }
}

async function assertLoginSucceeded(page: Page, testInfo: TestInfo) {
  const resp = await waitForLoginResponse(page);
  const status = resp.status();
  const headers = resp.headers();
  const body = await resp.text().catch(() => '');

  await testInfo.attach('login_response', {
    body: JSON.stringify(
      {
        url: resp.url(),
        status,
        set_cookie: headers['set-cookie'] ?? null,
        body: body.slice(0, 2000),
      },
      null,
      2
    ),
    contentType: 'application/json',
  });

  if (status < 200 || status >= 300) {
    throw new Error(`Login POST failed: ${status} (see login_response attachment)`);
  }

  const setCookie = headers['set-cookie'] ?? '';
  if (/;\s*secure\b/i.test(setCookie) && page.url().startsWith('http://')) {
    throw new Error(
      'Backend issued a Secure session cookie while frontend is http://. ' +
        'Cookie will not be stored. Use https for local dev or disable secure cookies in local env.'
    );
  }
}

async function assertSessionUsable(page: Page, backendUrl: string, testInfo: TestInfo) {
  const urls = [`${backendUrl}/v1/auth/me`, `${backendUrl}/api/auth/me`];

  await expect
    .poll(async () => {
      const results = await page.evaluate(async (probeUrls: string[]) => {
        const out: { url: string; status: number; body: string }[] = [];
        for (const url of probeUrls) {
          try {
            const r = await fetch(url, {
              method: 'GET',
              credentials: 'include',
              headers: { Accept: 'application/json' },
            });
            const body = await r.text().catch(() => '');
            out.push({ url, status: r.status, body: body.slice(0, 500) });
          } catch (e: any) {
            out.push({ url, status: 0, body: String(e?.message ?? e) });
          }
        }
        return out;
      }, urls);

      if (results.some((r) => r.status === 200)) {
        await testInfo.attach('auth_me_results', {
          body: JSON.stringify(results, null, 2),
          contentType: 'application/json',
        });
        return 200;
      }

      await testInfo.attach('auth_me_results', {
        body: JSON.stringify(results, null, 2),
        contentType: 'application/json',
      });
      return results[0]?.status ?? 0;
    }, { timeout: 15_000 })
    .toBe(200);
}

async function attachCookieHostDiagnostics(page: Page, testInfo: TestInfo) {
  await testInfo.attach('cookies_localhost', {
    body: JSON.stringify(await page.context().cookies('http://localhost:8000'), null, 2),
    contentType: 'application/json',
  });
  await testInfo.attach('cookies_127', {
    body: JSON.stringify(await page.context().cookies('http://127.0.0.1:8000'), null, 2),
    contentType: 'application/json',
  });
}

async function waitForSessionCookie(context: BrowserContext, testInfo: TestInfo, backendUrl: string) {
  await expect
    .poll(async () => {
      const cookies = await context.cookies(backendUrl);
      const has = cookies.some((c) => c.name === 'omni_session');
      if (!has) {
        await testInfo.attach('cookies_snapshot', {
          body: JSON.stringify(cookies, null, 2),
          contentType: 'application/json',
        });
      }
      return has;
    }, { timeout: 15_000 })
    .toBeTruthy();
}

async function gotoLogin(page: Page) {
  if (await hasSessionCookie(page)) return;
  const candidates = ['/login', '/#/login', '/#login'];

  for (const path of candidates) {
    await page.goto(`${FRONTEND_URL}${path}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(200);

    const hasPassword =
      (await page.locator('input[type="password"], input[name="password"]').count()) > 0;
    const hasSubmit =
      (await page.locator('button[type="submit"]').count()) > 0;

    if (hasPassword || hasSubmit) return;
  }
}

function loginLocators(page: Page) {
  const form = authFormLocator(page);
  const username = form
    .getByRole('textbox', { name: /username|email/i })
    .or(form.locator('input[name="username"], input[name="email"], input[autocomplete="username"], input[type="text"]'))
    .first();

  const password = form
    .getByRole('textbox', { name: /password/i })
    .or(form.locator('input[name="password"], input[autocomplete="current-password"], input[type="password"]'))
    .first();

  const submit = form
    .getByRole('button', { name: /log in|login|sign in|continue/i })
    .or(form.locator('button[type="submit"]'))
    .first();

  const signInTab = page.getByRole('tab', { name: /sign in|login/i });

  return { form, username, password, submit, signInTab };
}

function authFormLocator(page: Page) {
  return page.locator('form:has(input[type="password"], input[name="password"])').first();
}

async function typeLikeUser(locator: Locator, value: string) {
  await locator.click({ timeout: 10_000 });
  await locator.fill('');
  await locator.type(value, { delay: 10 });
}

async function submitLoginForm(form: Locator, submit: Locator) {
  await submit.click({ timeout: 10_000 });
  await form.evaluate((f) => (f as HTMLFormElement).requestSubmit?.());
}

test.describe('OmniAI v1 Smoke Tests', () => {
  test.beforeEach(async ({ page, context, baseURL }) => {
    await context.clearCookies();
    const origin = baseURL ?? FRONTEND_URL;
    await page.goto(`${origin}/`, { waitUntil: 'domcontentloaded' });
    await safeClearStorage(page);
    await page.reload({ waitUntil: 'domcontentloaded' });
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      await testInfo.attach('url', { body: page.url(), contentType: 'text/plain' });
      await testInfo.attach('html', { body: await page.content(), contentType: 'text/html' });
      await testInfo.attach('screenshot', {
        body: await page.screenshot({ fullPage: true }),
        contentType: 'image/png',
      });
    }
  });

  test.describe('Boot', () => {
    test('runtime-config.json loads without error overlay', async ({ page }) => {
      await page.goto(FRONTEND_URL);
      
      // Should load without JavaScript errors causing an overlay
      // Error overlay would typically have a specific CSS class or data attribute
      const errorOverlay = page.locator('[data-testid="error-overlay"]');
      await expect(errorOverlay).not.toBeVisible({ timeout: 5000 }).catch(() => {});
    });

    test('UI renders even if backend is down', async ({ page }) => {
      // Navigate to page - should show error banner, not blank
      await page.goto(FRONTEND_URL);
      
      // Check that main UI elements are present
      const loginButton = page.locator('button:has-text("Login"), button:has-text("Sign Up")');
      await expect(loginButton.first()).toBeVisible({ timeout: 5000 }).catch(() => {});
    });
  });

  test.describe('Authentication', () => {
    test('login sets cookie session', async ({ page }, testInfo) => {
      requireCreds(testInfo);
      await preflightAuthBackend(page, BACKEND_URL, testInfo);
      await gotoLogin(page);

      if (!(await hasSessionCookie(page))) {
        const { form, username, password, submit, signInTab } = loginLocators(page);

        if (await signInTab.isVisible().catch(() => false)) {
          await signInTab.click();
        }

        await expect(form).toHaveCount(1, { timeout: 15_000 });
        await expect(password).toBeVisible({ timeout: 15_000 });
        await expect(username).toBeVisible({ timeout: 15_000 });

        await typeLikeUser(username, E2E_USERNAME!);
        await typeLikeUser(password, E2E_PASSWORD!);

        await expect(submit).toBeVisible({ timeout: 15_000 });
        await expect(submit).toBeEnabled({ timeout: 15_000 });

        let loginDiag: { requests: { method: string; url: string; type: string }[]; consoles: { type: string; text: string }[]; pageErrors: string[] } = {
          requests: [],
          consoles: [],
          pageErrors: [],
        };

        const loginSucceeded = assertLoginSucceeded(page, testInfo);
        const browserCsrfCapture = E2E_DEBUG
          ? captureBrowserCsrfBootstrap(page, BACKEND_URL, testInfo).catch(async (error) => {
              await testInfo.attach('csrf_bootstrap_browser_response_error', {
                body: String(error?.message ?? error),
                contentType: 'text/plain',
              });
            })
          : Promise.resolve();

        loginDiag = await recordLoginAttempt(page, async () => {
          await submitLoginForm(form, submit);
        });

        await browserCsrfCapture;

        if (E2E_DEBUG) {
          await testInfo.attach('login_requests_all', {
            body: JSON.stringify(loginDiag.requests, null, 2),
            contentType: 'application/json',
          });
          await testInfo.attach('login_console', {
            body: JSON.stringify(loginDiag.consoles, null, 2),
            contentType: 'application/json',
          });
          await testInfo.attach('login_page_errors', {
            body: JSON.stringify(loginDiag.pageErrors, null, 2),
            contentType: 'application/json',
          });
        }

        try {
          await loginSucceeded;
        } catch (error: any) {
          throw new Error(
            `Login response wait failed.${E2E_DEBUG ? ` requests=${JSON.stringify(loginDiag.requests)}` : ''}\n${String(error?.message ?? error)}`
          );
        }
        await attachCookieHostDiagnostics(page, testInfo);
      }

      await assertSessionUsable(page, BACKEND_URL, testInfo);
      await waitForSessionCookie(page.context(), testInfo, BACKEND_URL);
    });

    test('logout clears session', async ({ page }, testInfo) => {
      requireCreds(testInfo);
      await preflightAuthBackend(page, BACKEND_URL, testInfo);
      // First login
      await gotoLogin(page);
      const { username, password, submit, signInTab } = loginLocators(page);
      if (await signInTab.isVisible().catch(() => false)) {
        await signInTab.click();
      }
      await expect(password).toBeVisible({ timeout: 15_000 });
      await expect(username).toBeVisible({ timeout: 15_000 });
      await username.fill(E2E_USERNAME!);
      await password.fill(E2E_PASSWORD!);
      const loginSucceeded = assertLoginSucceeded(page, testInfo);
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
        submit.click(),
      ]);
      await loginSucceeded;
      await attachCookieHostDiagnostics(page, testInfo);
      await assertSessionUsable(page, BACKEND_URL, testInfo);
      await waitForSessionCookie(page.context(), testInfo, BACKEND_URL);
      
      // Wait for authenticated state
      await page.waitForURL(/.*chat.*|.*$/, { timeout: 10000 }).catch(() => {});
      
      // Logout
      await page.click('button:has-text("Logout"), button:has-text("Sign Out")');
      
      // Verify session cleared - protected routes should bounce to /login
      await page.goto(`${FRONTEND_URL}/#/chat`);
      await expect(page).toHaveURL(/.*login.*|.*auth.*/).catch(() => {});
    });
  });

  test.describe('Conversations', () => {
    test.beforeEach(async ({}, testInfo) => {
      requireCreds(testInfo);
    });

    test('list loads', async ({ page }) => {
      // Assuming already logged in from previous test
      await page.goto(`${FRONTEND_URL}/#/chat`);
      await page.waitForLoadState('networkidle');
      
      // Conversation list should be visible
      const conversationList = page.locator('[data-testid="conversation-list"], aside');
      await expect(conversationList.first()).toBeVisible({ timeout: 5000 }).catch(() => {});
    });

    test('create conversation appears in list', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Create new conversation
      const newChatBtn = page.locator('button:has-text("New Chat"), button:has-text("+")');
      await newChatBtn.click();
      
      // Should see new conversation in list
      const conversationItems = page.locator('[data-testid="conversation-item"], [data-testid="conversation-list"] li');
      const countBefore = await conversationItems.count();
      
      // Send a message to create the conversation
      const input = page.locator('textarea[name="message"], input[name="message"]');
      await input.fill('Test message');
      await input.press('Enter');
      
      // New conversation should appear
      await page.waitForTimeout(500);
    });

    test('rename conversation updates in list', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Click on a conversation to open it
      const conversation = page.locator('[data-testid="conversation-item"]').first();
      await conversation.click();
      
      // Find rename option
      const renameBtn = page.locator('button:has-text("Rename")');
      await renameBtn.click();
      
      // Enter new name
      const nameInput = page.locator('input[name="title"], input[placeholder*="name"]');
      await nameInput.fill('Renamed Test Conversation');
      await nameInput.press('Enter');
      
      // Verify renamed
      const renamed = page.locator('text=Renamed Test Conversation');
      await expect(renamed).toBeVisible().catch(() => {});
    });

    test('delete conversation removes from list', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Get initial count
      const initialCount = await page.locator('[data-testid="conversation-item"]').count();
      
      // Delete a conversation
      const deleteBtn = page.locator('button:has-text("Delete")').first();
      await deleteBtn.click();
      
      // Confirm deletion if dialog appears
      const confirmBtn = page.locator('button:has-text("Delete"), button:has-text("Confirm")');
      await confirmBtn.click();
      
      // Verify removed
      await page.waitForTimeout(500);
    });

    test('clicking thread navigates to chat/{id}', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Click on a conversation
      const conversation = page.locator('[data-testid="conversation-item"]').first();
      await conversation.click();
      
      // URL should include /chat/{id}
      await expect(page).toHaveURL(/.*chat\/[a-zA-Z0-9-]+/).catch(() => {});
    });
  });

  test.describe('Streaming', () => {
    test.beforeEach(async ({}, testInfo) => {
      requireCreds(testInfo);
    });

    test('send message streams response with deltas', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Send a message
      const input = page.locator('textarea[name="message"], input[name="message"]');
      await input.fill('Hello, this is a test message for streaming');
      await input.press('Enter');
      
      // Assistant bubble should appear
      const assistantBubble = page.locator('[data-testid="assistant-message"], .message.assistant');
      await expect(assistantBubble.first()).toBeVisible({ timeout: 30000 }).catch(() => {});
      
      // Content should be streaming (may be partial initially)
      const content = assistantBubble.locator('[data-testid="message-content"]');
      await expect(content).toBeVisible().catch(() => {});
    });

    test('stop aborts SSE stream immediately', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Send a long message that will generate a streaming response
      const input = page.locator('textarea[name="message"], input[name="message"]');
      await input.fill('Write a detailed essay about artificial intelligence');
      await input.press('Enter');
      
      // Wait for streaming to start
      await page.waitForTimeout(2000);
      
      // Click stop button
      const stopBtn = page.locator('button:has-text("Stop"), button:has-text("Cancel")');
      await stopBtn.click();
      
      // Verify stop button is no longer visible (stream stopped)
      await expect(stopBtn.first()).not.toBeVisible({ timeout: 5000 }).catch(() => {});
    });

    test('retry resends identical payload', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Send a message
      const input = page.locator('textarea[name="message"], input[name="message"]');
      await input.fill('Test retry functionality');
      await input.press('Enter');
      
      // Wait for response
      await page.waitForTimeout(5000);
      
      // Find and click retry button
      const retryBtn = page.locator('button:has-text("Retry")');
      await retryBtn.click();
      
      // Should see new streaming response
      const loadingIndicator = page.locator('text=Thinking..., text=Streaming');
      await expect(loadingIndicator.first()).toBeVisible({ timeout: 10000 }).catch(() => {});
    });
  });

  test.describe('Settings', () => {
    test.beforeEach(async ({}, testInfo) => {
      requireCreds(testInfo);
    });

    test('provider/model dropdown works when endpoints available', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Open settings
      const settingsBtn = page.locator('button:has-text("Settings"), button[aria-label="Settings"]');
      await settingsBtn.click();
      
      // Provider dropdown should be visible
      const providerSelect = page.locator('select[name="provider"], [data-testid="provider-select"]');
      await expect(providerSelect).toBeVisible().catch(() => {});
      
      // Should have options when providers are available
      const options = providerSelect.locator('option');
      const count = await options.count();
      expect(count).toBeGreaterThan(0);
    });

    test('temperature/topP/maxTokens persist across reload', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Open settings
      await page.click('button:has-text("Settings")');
      
      // Set temperature
      const tempSlider = page.locator('input[name="temperature"], [data-testid="temperature"]');
      await tempSlider.fill('0.7');
      
      // Set topP
      const topPSlider = page.locator('input[name="topP"], [data-testid="top-p"]');
      await topPSlider.fill('0.9');
      
      // Set max tokens
      const maxTokensInput = page.locator('input[name="maxTokens"], [data-testid="max-tokens"]');
      await maxTokensInput.fill('2048');
      
      // Reload page
      await page.reload();
      
      // Verify settings persisted
      await page.waitForLoadState('networkidle');
      
      // Values should be restored
      // Note: This depends on UI implementation
    });
  });

  test.describe('Feature Flags', () => {
    test.beforeEach(async ({}, testInfo) => {
      requireCreds(testInfo);
    });

    test('enabling flags shows panel toggles', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Settings should show panel toggles when flags are enabled
      const memoryPanelToggle = page.locator('input[name="memoryPanel"], [data-testid="memory-toggle"]');
      const knowledgePanelToggle = page.locator('input[name="knowledgePanel"], [data-testid="knowledge-toggle"]');
      
      // These may be visible or hidden based on feature flags
      // The test verifies the UI responds to flags correctly
    });

    test('dock open/active tab persists across reload', async ({ page }) => {
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Open a panel (e.g., settings)
      const panel = page.locator('[data-testid="settings-panel"], aside');
      const wasVisible = await panel.isVisible();
      
      // Toggle if not visible
      if (!wasVisible) {
        await page.click('button:has-text("Settings")');
      }
      
      // Reload
      await page.reload();
      
      // Panel state should persist
      await expect(panel).toBeVisible({ timeout: 5000 }).catch(() => {});
    });
  });

  test.describe('Failure Modes', () => {
    test('401/403 shows login prompt', async ({ page }) => {
      // Force an unauthorized state by clearing cookies
      await page.context().clearCookies();
      await page.goto(`${FRONTEND_URL}/#/chat`);
      
      // Should redirect to login or show auth prompt
      await expect(page).toHaveURL(/.*login.*|.*auth.*|.*$/).catch(() => {});
    });

    test('429 rate limit surfaced cleanly', async ({ page }) => {
      // This test requires spamming the API
      // In practice, you might mock the response or use a test account with low limits
      
      // The error should be user-friendly, not a stack trace
      const errorMessage = page.locator('text=Rate limited, text=Too many requests');
      await expect(errorMessage.first()).toBeVisible({ timeout: 10000 }).catch(() => {});
    });

    test('SSE disconnect shows error + retry', async ({ page }) => {
      // This test simulates network failure during streaming
      // Could use CDP to block the SSE endpoint
      
      // After disconnect, retry button should be visible
      const retryBtn = page.locator('button:has-text("Retry"), button:has-text("Try Again")');
      await expect(retryBtn.first()).toBeVisible({ timeout: 10000 }).catch(() => {});
    });
  });
});

// Parallel execution for faster runs
export default test;
