"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getAuthToken, setAuthToken, setUnauthorizedHandler } from "@/lib/api";

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

    if (getAuthToken()) {
      apiFetch<AuthUser>("/api/auth/me")
        .then((me) => {
          if (!cancelled) setUser(me);
        })
        .catch(() => {
          // apiFetch already cleared the stored token on a 401; this just
          // syncs local state (also covers network errors, where it doesn't).
          if (!cancelled) {
            setToken(null);
            setUser(null);
          }
        })
        .finally(() => {
          if (!cancelled) setInitializing(false);
        });
    }

    return () => {
      cancelled = true;
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
