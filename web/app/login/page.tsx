"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import PageHeader from "@/components/PageHeader";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusText, setStatusText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatusText("Logging in...");
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (e) {
      const message = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
      setStatusText("Error: " + message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader breadcrumb="Log In" title="Log In" subtitle="Access your Content Engine workspace." action={null} />

      <div className="panel form-panel" style={{ maxWidth: 420 }}>
        <div className="panel-header">
          <h2>Welcome back</h2>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label" htmlFor="login-email">
              Email
            </label>
            <input
              type="email"
              id="login-email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="login-password">
              Password
            </label>
            <input
              type="password"
              id="login-password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button type="submit" className="btn-run" disabled={submitting}>
            <span className="btn-run-inner">Log In</span>
          </button>
          <div className="status-text">{statusText}</div>
        </form>
      </div>

      <p className="meta-line" style={{ marginTop: 16 }}>
        Don&apos;t have an account? <Link href="/signup">Sign up</Link>
      </p>
    </>
  );
}
