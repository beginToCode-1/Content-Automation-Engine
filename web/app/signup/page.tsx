"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import PageHeader from "@/components/PageHeader";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [statusText, setStatusText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatusText("Creating account...");
    setSubmitting(true);
    try {
      await register(email, password);
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
      <PageHeader breadcrumb="Sign Up" title="Create an Account" subtitle="Set up access to your Content Engine workspace." action={null} />

      <div className="info-banner">
        <span className="info-banner-icon">i</span>
        <span className="info-banner-text">
          First person to sign up becomes admin. Everyone who signs up after that gets read-only viewer access until
          an admin says otherwise.
        </span>
      </div>

      <div className="panel form-panel" style={{ maxWidth: 420 }}>
        <div className="panel-header">
          <h2>Create your account</h2>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label" htmlFor="signup-email">
              Email
            </label>
            <input
              type="email"
              id="signup-email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="signup-password">
              Password
            </label>
            <input
              type="password"
              id="signup-password"
              name="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={72}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div className="field-hint">8-72 characters.</div>
          </div>

          <button type="submit" className="btn-run" disabled={submitting}>
            <span className="btn-run-inner">Sign Up</span>
          </button>
          <div className="status-text">{statusText}</div>
        </form>
      </div>

      <p className="meta-line" style={{ marginTop: 16 }}>
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </>
  );
}
