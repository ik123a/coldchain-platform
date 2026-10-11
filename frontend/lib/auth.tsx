"use client";
// Auth: token storage + login/register/me. The backend already implements
// POST /api/auth/register, POST /api/auth/login and GET /api/auth/me (JWT bearer,
// pbkdf2 hashing). The only missing piece was the client side — this file is it.
//
// Token lives in localStorage so it survives reloads; api() reads it on every
// request and attaches the Authorization header. When a 401 comes back the
// session is cleared and the user is bounced to /login.
import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";

export const TOKEN_KEY = "cc_token";
export const USER_KEY = "cc_user";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role?: "operator" | "driver" | string;
  vehicle_id?: string | null;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setSession(token: string, user: AuthUser) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {}
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {}
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

// --- raw auth calls (deliberately NOT using api() to avoid a circular import
// between api.ts (which reads the token) and this module (which writes it)). ---

async function authFetch(path: string, body?: unknown, token?: string | null) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, {
    method: "POST",
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const text = await res.text().catch(() => "");
  let json: any = {};
  try {
    json = text ? JSON.parse(text) : {};
  } catch {
    json = {};
  }
  if (!res.ok) {
    const detail = json?.detail || json?.message || text.slice(0, 160) || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return json;
}

export async function login(email: string, password: string) {
  const out = await authFetch("/api/auth/login", { email, password });
  setSession(out.access_token, out.user);
  return out.user as AuthUser;
}

export async function register(name: string, email: string, password: string,
                               role: string = "operator", vehicleId?: string | null) {
  const out = await authFetch("/api/auth/register", { name, email, password, role,
                                                      vehicle_id: vehicleId ?? null });
  setSession(out.access_token, out.user);
  return out.user as AuthUser;
}

export async function claimTruck(vehicleId: string): Promise<AuthUser> {
  const token = getToken();
  const out = await authFetch("/api/auth/claim-truck", { vehicle_id: vehicleId }, token);
  // Refresh the cached user so the driver UI sees the bound truck immediately.
  const u = await fetchMe();
  if (u) setSession(getToken() || "", u);
  return (u as AuthUser) || out;
}

export async function availableTrucks(): Promise<
  { vehicle_id: string; driver_name: string; cargo_type: string; taken?: boolean }[]
> {
  const token = getToken();
  const res = await fetch("/api/auth/available-trucks", {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  if (!res.ok) return [];
  const j = await res.json().catch(() => ({ trucks: [] }));
  return j.trucks || [];
}

export async function fetchMe(): Promise<AuthUser | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      clearSession();
      return null;
    }
    return (await res.json()) as AuthUser;
  } catch {
    return null;
  }
}

export function logout() {
  clearSession();
  if (typeof window !== "undefined") window.location.href = "/login";
}

// --- React context -----------------------------------------------------------

interface AuthCtx {
  user: AuthUser | null;
  ready: boolean; // false until the initial token check completes
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string, role?: string, vehicleId?: string | null) => Promise<void>;
  signOut: () => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    const u = await fetchMe();
    if (u) {
      setUser(u);
      setSession(getToken() || "", u);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    // Optimistically show the cached user, then confirm against the server.
    const cached = getUser();
    if (cached) setUser(cached);
    fetchMe().then((u) => {
      if (!alive) return;
      if (u) {
        setUser(u);
        setSession(getToken() || "", u);
      } else if (!getToken()) {
        setUser(null);
      }
      setReady(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const u = await login(email, password);
    setUser(u);
  }, []);

  const signUp = useCallback(async (name: string, email: string, password: string,
                                    role: string = "operator", vehicleId?: string | null) => {
    const u = await register(name, email, password, role, vehicleId);
    setUser(u);
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
    if (typeof window !== "undefined") window.location.href = "/login";
  }, []);

  return (
    <Ctx.Provider value={{ user, ready, signIn, signUp, signOut, refresh }}>{children}</Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside <AuthProvider>");
  return c;
}
