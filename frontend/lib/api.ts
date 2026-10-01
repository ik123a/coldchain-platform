// HTTP goes through the Next dev-server proxy (see next.config.mjs rewrites),
// so requests are same-origin. Calling the backend directly from the browser
// made every response cross-origin: a 5xx without CORS headers surfaces as
// ERR_FAILED and is indistinguishable from a network outage. Override with
// NEXT_PUBLIC_API_URL only when the backend is served from another host.
const API = process.env.NEXT_PUBLIC_API_URL || "";

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? " — " + text.slice(0, 160) : ""}`);
  }
  return res.json().catch(() => ({} as T));
}

export const post = <T = any>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, { method: "POST", body: body != null ? JSON.stringify(body) : undefined });

export const API_BASE = API;
// The WebSocket is deliberately NOT proxied — Next's rewrites do not carry an
// Upgrade, so a ws:// origin URL connects but never receives frames (verified:
// 57 messages direct, 0 through the proxy). Keep it on the backend origin.
export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000/ws";
