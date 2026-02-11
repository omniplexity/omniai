import type { APIRequestContext, BrowserContext } from "@playwright/test";

export async function apiLogin(params: {
  request: APIRequestContext;
  context: BrowserContext;
  backendUrl: string;
  username: string;
  password: string;
  frontendOrigin: string;
}): Promise<void> {
  const csrfRes = await params.request.get(`${params.backendUrl}/v1/auth/csrf/bootstrap`, {
    headers: { Origin: params.frontendOrigin },
  });
  if (!csrfRes.ok()) {
    throw new Error(`CSRF bootstrap failed: ${csrfRes.status()}`);
  }
  const body = (await csrfRes.json()) as { csrf_token?: string };
  const csrf = body.csrf_token;
  if (!csrf) throw new Error("CSRF bootstrap returned no csrf_token");

  const loginRes = await params.request.post(`${params.backendUrl}/v1/auth/login`, {
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      Origin: params.frontendOrigin,
    },
    data: {
      username: params.username,
      password: params.password,
    },
  });
  if (!loginRes.ok()) {
    const txt = await loginRes.text();
    throw new Error(`API login failed: ${loginRes.status()} ${txt}`);
  }

  const storage = await params.request.storageState();
  await params.context.addCookies(storage.cookies);
}
