"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Droplets, Loader2, ShieldCheck, AlertTriangle } from "lucide-react";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const { user, ready, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<"operator" | "driver">("operator");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Already authenticated → no reason to sit on the login screen. Drivers land
  // on their own truck view; operators on the fleet dashboard.
  useEffect(() => {
    if (ready && user) router.replace(user.role === "driver" ? "/driver" : "/dashboard");
  }, [ready, user, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setErr(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await signIn(email.trim(), password);
      } else {
        await signUp(name.trim(), email.trim(), password, role);
      }
      // Role is known either from the response or the stored session.
      const stored = typeof window !== "undefined" ? localStorage.getItem("cc_user") : null;
      const r = stored ? JSON.parse(stored).role : role;
      router.replace(r === "driver" ? "/driver" : "/dashboard");
    } catch (e: any) {
      const msg = String(e?.message || e);
      // The backend returns {"detail": "..."} — surface it plainly.
      setErr(
        msg.includes("invalid credentials")
          ? "Invalid email or password."
          : msg.includes("already registered")
          ? "That email is already registered — try signing in."
          : msg
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-[var(--canvas)] p-4 text-[var(--text)]">
      <div className="w-full max-w-[400px]">
        <div className="mb-6 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-[12px] border border-[var(--border-accent)] bg-gradient-to-br from-[#1E3A5F] to-[#0D1623]">
            <Droplets size={18} className="text-[var(--accent)]" />
          </span>
          <div className="leading-tight">
            <p className="t-body font-bold tracking-tight text-[var(--text)]">COLDCHAIN RESCUE</p>
            <p className="t-micro tracking-wider text-[var(--text-muted)]">AI COLD-CHAIN COMMAND CENTER</p>
          </div>
        </div>

        <div className="rounded-[var(--r-lg)] border border-[var(--border)] bg-[var(--surface-card)] p-6 shadow-[0_18px_50px_-24px_rgba(0,0,0,0.55)]">
          <div
            role="tablist"
            aria-label="Account mode"
            className="mb-5 flex rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-inset)] p-1"
          >
            {(["login", "register"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => {
                  setMode(m);
                  setErr(null);
                }}
                className={`flex-1 rounded-[var(--r-sm)] px-3 py-2 t-body-sm font-semibold transition-colors ${
                  mode === m
                    ? "border border-[var(--border-strong)] bg-[var(--surface-card)] text-[var(--text)] shadow-sm"
                    : "border border-transparent text-[var(--text-muted)] hover:text-[var(--text)]"
                }`}
              >
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-3">
            {mode === "register" && (
              <Field
                label="Name"
                value={name}
                onChange={setName}
                type="text"
                placeholder="Aarav Sharma"
                autoComplete="name"
                required
                minLength={2}
              />
            )}
            <Field
              label="Email"
              value={email}
              onChange={setEmail}
              type="email"
              placeholder="operator@coldchain.io"
              autoComplete="email"
              required
            />
            <Field
              label="Password"
              value={password}
              onChange={setPassword}
              type="password"
              placeholder={mode === "register" ? "at least 6 characters" : "••••••••"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "register" ? 6 : undefined}
            />

            {mode === "register" && (
              <div>
                <span className="ops-label mb-1 block">I am a</span>
                <div className="flex rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-inset)] p-1">
                  {(["operator", "driver"] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setRole(r)}
                      className={`flex-1 rounded-[var(--r-sm)] px-3 py-1.5 t-body-sm font-semibold transition-colors ${
                        role === r
                          ? "border border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-on)] font-bold"
                          : "border border-transparent text-[var(--text-muted)] hover:text-[var(--text)]"
                      }`}
                    >
                      {r === "operator" ? "Operator" : "Truck driver"}
                    </button>
                  ))}
                </div>
                <p className="mt-1.5 t-body-sm leading-relaxed text-[var(--text-muted)]">
                  {role === "driver"
                    ? "You'll be asked which truck you drive, then see that truck only."
                    : "You'll see the whole fleet, incidents and approvals."}
                </p>
              </div>
            )}

            {err && (
              <div className="flex items-start gap-2 rounded-[var(--r-md)] border border-[var(--critical)] bg-[var(--surface-inset)] px-3 py-2">
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--critical)]" />
                <p className="t-body-sm text-[var(--critical)]">{err}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-[var(--r-md)] border border-[var(--accent)] bg-[var(--accent)] px-3 py-2.5 t-body-sm font-bold text-[var(--accent-on)] transition-[filter] hover:brightness-110 disabled:opacity-60"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              {mode === "login" ? "Sign in" : "Create account & sign in"}
            </button>
          </form>
        </div>

        <div className="mt-4 flex items-start gap-2 px-2">
          <ShieldCheck size={13} className="mt-0.5 shrink-0 text-[var(--text-muted)]" />
          <p className="t-micro leading-relaxed text-[var(--text-muted)]">
            JWT-authenticated session · role-scoped operational API · simulation environment.
            Accounts are stored in the local database; no email verification is required.
          </p>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type,
  placeholder,
  autoComplete,
  required,
  minLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type: string;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
}) {
  return (
    <label className="block">
      <span className="ops-label mb-1 block">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        className="w-full rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-inset)] px-3 py-2 t-body-sm text-[var(--text)] outline-none transition-colors placeholder:text-[var(--text-dim)] focus:border-[var(--accent)]"
      />
    </label>
  );
}
