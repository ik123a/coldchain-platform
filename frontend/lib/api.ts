const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || API.replace(/^http/, "ws") + "/ws";
