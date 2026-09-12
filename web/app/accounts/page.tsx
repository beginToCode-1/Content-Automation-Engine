"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import PageHeader from "@/components/PageHeader";
import RelativeTime from "@/components/RelativeTime";
import { apiFetch, apiUrl, type Account } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Maps the backend OAuth callback's ?error= reason codes (api_oauth.py's
// callback redirects to /accounts?error=<reason> on failure) to copy a user
// can act on. Falls back to a generic message for anything not in this list
// (currently a raw Google error code can also land here).
const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "You declined the Google permission request.",
  missing_code: "Google didn't return an authorization code - please try again.",
  invalid_state: "That connection attempt expired or was invalid - please try again.",
  connect_failed: "Couldn't connect that account - please try again.",
};

function errorMessage(code: string): string {
  return ERROR_MESSAGES[code] || `Couldn't connect that account (${code}) - please try again.`;
}

interface Banner {
  kind: "success" | "error";
  text: string;
}

function AccountsPageInner() {
  const searchParams = useSearchParams();
  const { user, token } = useAuth();
  // Connected accounts determine who a run/batch/schedule/self-upload can
  // publish to and are tied to the connecting admin's own Google credential,
  // so - matching this app's existing "admin has full access, viewer is
  // read-only" convention (see other pages' `isAdmin` checks) - a viewer can
  // still see the read-only list below, but not connect or disconnect.
  const isAdmin = user?.role === "admin";

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusText, setStatusText] = useState("");
  const [removingId, setRemovingId] = useState<string | null>(null);
  // One-time banner from the OAuth callback redirect (?connected=youtube or
  // ?error=<reason>) - computed synchronously from the URL search params
  // available on first render, rather than in an effect, so it can't trigger
  // a second cascading render.
  const [banner, setBanner] = useState<Banner | null>(() => {
    const connected = searchParams.get("connected");
    const error = searchParams.get("error");
    if (connected === "youtube") return { kind: "success", text: "YouTube account connected." };
    if (error) return { kind: "error", text: errorMessage(error) };
    return null;
  });

  // Strip ?connected=/?error= from the URL after reading them above, so a
  // refresh or back-navigation doesn't re-show the banner. This is a side
  // effect on the browser's history, not on React state, so it belongs in
  // an effect even though the value it read is only used once.
  useEffect(() => {
    if (searchParams.get("connected") || searchParams.get("error")) {
      window.history.replaceState(null, "", "/accounts");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ accounts: Account[] }>("/api/accounts")
      .then((data) => {
        if (!cancelled) setAccounts(data.accounts);
      })
      .catch((e) => {
        if (!cancelled) setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleConnect() {
    // The final navigation to the backend has to be a full browser redirect
    // (Google's consent screen redirects back to our own backend, so there's
    // no way to attach a fetch Authorization header the way the rest of the
    // app does) - but we still fetch a short-lived, single-purpose ticket
    // first via a normal authenticated apiFetch() call, rather than putting
    // the long-lived session token itself in the URL (server logs, browser
    // history, and any Referer header would otherwise see it).
    if (!token) return;
    try {
      const { ticket } = await apiFetch<{ ticket: string }>("/api/oauth/youtube/connect-ticket", {
        method: "POST",
      });
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `${apiUrl("/api/oauth/youtube/connect")}?ticket=${ticket}`;
    } catch (e) {
      setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  async function handleDisconnect(account: Account) {
    if (!window.confirm(`Disconnect "${account.account_label}"? Anything targeting it will need a different account.`)) {
      return;
    }
    setRemovingId(account.id);
    setStatusText("");
    try {
      await apiFetch<{ deleted: boolean }>(`/api/accounts/${account.id}`, { method: "DELETE" });
      setAccounts((prev) => prev.filter((a) => a.id !== account.id));
    } catch (e) {
      setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setRemovingId(null);
    }
  }

  const youtubeAccounts = accounts.filter((a) => a.platform === "youtube");

  return (
    <>
      <PageHeader
        breadcrumb="Accounts"
        title="Connected Accounts"
        subtitle="Connect your own YouTube channel(s) and choose which one each run publishes to."
        action={null}
      />

      {banner && (
        <div
          className="info-banner"
          style={banner.kind === "error" ? { background: "var(--danger-soft)" } : undefined}
        >
          <span
            className="info-banner-icon"
            style={banner.kind === "error" ? { background: "var(--danger)" } : undefined}
          >
            {banner.kind === "error" ? "!" : "i"}
          </span>
          <span className="info-banner-text">{banner.text}</span>
          <button
            type="button"
            className="btn-icon"
            aria-label="Dismiss"
            onClick={() => setBanner(null)}
            style={{ marginLeft: "auto", width: 24, height: 24, flexShrink: 0 }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
              <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      )}

      {!isAdmin && (
        <p className="note" style={{ marginBottom: 20 }}>
          Admin access required to connect or disconnect accounts. You can still review connected accounts below.
        </p>
      )}

      <div className="panel form-panel">
        <div className="panel-header">
          <h2>YouTube</h2>
          {isAdmin && (
            <button type="button" className="btn-secondary" onClick={handleConnect}>
              Connect YouTube
            </button>
          )}
        </div>

        {loading && <p className="meta-line">Loading...</p>}
        {!loading && youtubeAccounts.length === 0 && (
          <p className="meta-line">No YouTube accounts connected yet.</p>
        )}

        {!loading && youtubeAccounts.length > 0 && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {youtubeAccounts.map((account) => (
              <li
                key={account.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "12px 0",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 500, display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      className="icon-badge icon-yt"
                      style={{ width: 18, height: 18, fontSize: 10, display: "inline-flex" }}
                    >
                      YT
                    </span>
                    {account.account_label}
                  </div>
                  <div className="meta-line" style={{ fontSize: "0.78rem", marginTop: 2 }}>
                    {account.external_account_id} &middot; Connected <RelativeTime value={account.created_at} />
                  </div>
                </div>
                {isAdmin && (
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={removingId === account.id}
                    onClick={() => handleDisconnect(account)}
                    style={{ flexShrink: 0 }}
                  >
                    Disconnect
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {statusText && <div className="status-text" style={{ marginLeft: 0, marginTop: 10 }}>{statusText}</div>}
      </div>
    </>
  );
}

export default function AccountsPage() {
  return (
    <Suspense fallback={null}>
      <AccountsPageInner />
    </Suspense>
  );
}
