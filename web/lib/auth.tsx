"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiFetch, getAuthToken, setAuthToken, setUnauthorizedHandler } from "@/lib/api";

export type Role = "admin" | "viewer";

export interface AuthUser {
  id: number | string;
  email: string;
  role: Role;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  /** True while the stored token (if any) is being validated against GET /api/auth/me on mount. */
  initializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  // Lazily seeded from the synchronously-available module state (localStorage,
  // read once at import time by lib/api.ts) so there's no redundant setState
  // call for it once the effect below runs.
  const [token, setToken] = useState<string | null>(() => getAuthToken());
  const [initializing, setInitializing] = useState<boolean>(() => !!getAuthToken());

  const clearAuth = useCallback(() => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  // Validate any token persisted from a previous session, and wire up the
  // global "session expired mid-use" handler that lib/api.ts's apiFetch()
  // invokes on a 401 from an already-authenticated request.
  useEffect(() => {
    let cancelled = false;

    setUnauthorizedHandler(() => {
      clearAuth();
      router.replace("/login");
    });

    // Only a 401 means the saved session is invalid. Anything else (network
    // error, 502/503 while the free-plan backend wakes up) is retried for about
    // a minute and a half instead of bouncing a logged-in user to /login.
    const validate = (attempt: number) => {
      apiFetch<AuthUser>("/api/auth/me")
        .then((me) => {
          if (!cancelled) {
            setUser(me);
            setInitializing(false);
          }
        })
        .catch((err) => {
          if (cancelled) return;
          const unauthorized = err instanceof ApiError && err.status === 401;
          if (!unauthorized && attempt < 9) {
            retryTimer = setTimeout(() => validate(attempt + 1), 10000);
            return;
          }
          // apiFetch already cleared the stored token on a 401; this syncs local state.
          setToken(null);
          setUser(null);
          setInitializing(false);
        });
    };
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    if (getAuthToken()) validate(0);

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      setUnauthorizedHandler(null);
    };
  }, [clearAuth, router]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiFetch<AuthResponse>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const data = await apiFetch<AuthResponse>("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, initializing, login, register, logout }),
    [user, token, initializing, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
