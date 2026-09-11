"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

// Routes that work with no logged-in user: the auth pages themselves, plus
// the two static legal pages (server components, no data fetching, meant to
// stay reachable without an account).
const PUBLIC_PATHS = new Set(["/login", "/signup", "/privacy", "/terms"]);

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, initializing } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublicPath = PUBLIC_PATHS.has(pathname);
  const isAuthPage = pathname === "/login" || pathname === "/signup";

  useEffect(() => {
    if (initializing) return;
    if (!user && !isPublicPath) {
      router.replace("/login");
    } else if (user && isAuthPage) {
      // Already logged in - no reason to show the login/signup form.
      router.replace("/");
    }
  }, [initializing, user, isPublicPath, isAuthPage, router]);

  // Public pages render immediately regardless of auth state.
  if (isPublicPath) return <>{children}</>;

  // Every other page waits out the initial "is the stored token still valid"
  // check (and the redirect-away above) rather than flashing protected
  // content that's about to be yanked.
  if (initializing || !user) {
    return (
      <div className="preview-box" style={{ marginTop: 8 }}>
        <div className="preview-box-text">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
