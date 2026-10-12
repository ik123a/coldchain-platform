"use client";
// AuthGate — the client-side guard around every operational route.
//
// The backend auth (register/login/me + JWT) already works; before this existed
// there was no login page, so the app was open to anyone who could reach it and
// no Authorization header was ever sent. This closes that gap:
//   - /login renders bare (no sidebar), so the shell is not shown pre-auth;
//   - any other route waits for the token check, then redirects to /login if
//     there is no valid session.
import { useEffect, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Loader2 } from "lucide-react";
import Layout from "@/components/Layout";

export default function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { user, ready } = useAuth();

  const isPublic = path === "/login";
  const isDriverRoute = path === "/driver";
  const isDriver = user?.role === "driver";

  useEffect(() => {
    if (isPublic || !ready) return;
    if (!user) {
      router.replace("/login");
    } else if (isDriver && !isDriverRoute) {
      // A driver account is bound to one truck — keep them on their console.
      router.replace("/driver");
    }
  }, [isPublic, ready, user, isDriver, isDriverRoute, router]);

  // Public route: the login screen owns the whole viewport.
  if (isPublic) return <>{children}</>;

  // Still checking the stored token, or about to be redirected.
  if (!ready || !user || (isDriver && !isDriverRoute)) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--canvas)] text-[var(--text-muted)]">
        <div className="flex items-center gap-2 t-body-sm">
          <Loader2 size={15} className="animate-spin" />
          <span>Verifying session…</span>
        </div>
      </div>
    );
  }

  return <Layout>{children}</Layout>;
}
