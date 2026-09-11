"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, type Account } from "@/lib/api";

interface YouTubeAccountPickerProps {
  /** The platforms currently checked on the form - this renders nothing unless "youtube" is in it. */
  platforms: string[];
  /** Currently chosen youtube_account_id, or null if none chosen yet. */
  value: string | null;
  onChange: (accountId: string | null) => void;
}

// Shared "which connected YouTube channel should this publish to" UI, used
// identically by the new-run, batch, schedule, and self-upload-publish forms
// (every POST that accepts a platforms list can include "youtube" and now
// optionally accepts youtube_account_id).
//
// Mirrors the backend's own resolution rule so we don't duplicate its
// validation client-side: 0 connected accounts -> the POST 400s with a clear
// "Connect a YouTube account first" message - this component just adds a
// discoverability hint + link to /accounts. Exactly 1 -> auto-selected
// server-side even if youtube_account_id is omitted (we still send it, for
// clarity, and to show the account name). 2+ -> the caller must send an
// explicit youtube_account_id or the POST 400s - this renders a <select>.
export default function YouTubeAccountPicker({ platforms, value, onChange }: YouTubeAccountPickerProps) {
  const targetsYouTube = platforms.includes("youtube");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!targetsYouTube || loaded) return;
    let cancelled = false;
    apiFetch<{ accounts: Account[] }>("/api/accounts")
      .then((data) => {
        if (cancelled) return;
        setAccounts(data.accounts.filter((a) => a.platform === "youtube"));
        setLoaded(true);
      })
      .catch(() => {
        // This component is discoverability-only - if the fetch fails, the
        // form's own submit error handling still surfaces whatever the
        // backend's POST validation says.
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [targetsYouTube, loaded]);

  // With exactly one connected account, report it back to the caller so the
  // POST body includes it explicitly (harmless - matches what the backend
  // would auto-select anyway) and the "Publishing to" hint below can show it.
  useEffect(() => {
    if (accounts.length === 1 && value !== accounts[0].id) {
      onChange(accounts[0].id);
    }
  }, [accounts, value, onChange]);

  if (!targetsYouTube || !loaded) return null;

  if (accounts.length === 0) {
    return (
      <div className="field-hint" style={{ marginTop: 8 }}>
        No YouTube account connected - <Link href="/accounts">visit Connected Accounts to add one</Link>.
      </div>
    );
  }

  if (accounts.length === 1) {
    return (
      <div className="field-hint" style={{ marginTop: 8 }}>
        Publishing to: <strong>{accounts[0].account_label}</strong>
      </div>
    );
  }

  return (
    <div className="field" style={{ marginTop: 8 }}>
      <label className="field-label" htmlFor="youtube-account-select">
        YouTube account
      </label>
      <select
        id="youtube-account-select"
        className="platform-select"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        <option value="">Select an account...</option>
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.account_label}
          </option>
        ))}
      </select>
      <div className="field-hint">You have multiple YouTube accounts connected - choose which one to publish to.</div>
    </div>
  );
}
