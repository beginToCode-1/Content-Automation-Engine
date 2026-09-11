"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, type Channel } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function navClass(active: boolean): string {
  return active ? "active" : "";
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [runsCount, setRunsCount] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    // /api/meta requires auth now - nothing to show until AuthProvider has
    // validated a token and populated `user`.
    if (!user) return;
    let cancelled = false;
    apiFetch<{ channels: Channel[]; runs_count: number }>("/api/meta")
      .then((data) => {
        if (cancelled) return;
        setChannels(data.channels);
        setRunsCount(data.runs_count);
      })
      .catch(() => {
        // Sidebar chrome degrades gracefully if the backend isn't reachable yet.
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  useEffect(() => {
    // Reads a browser-only API (localStorage) that has no server-side
    // equivalent, so this can only run post-mount - exactly the persisted
    // sidebar-collapse behavior static/shell.js had (collapsed class applied
    // once client JS runs, not before).
    try {
      if (localStorage.getItem("sidebarCollapsed") === "true") {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setCollapsed(true);
      }
    } catch {
      // ignore
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("sidebarCollapsed", next ? "true" : "false");
      } catch {
        // ignore
      }
      return next;
    });
  }

  const isUpload = pathname === "/";
  const isStudio = pathname === "/studio";
  const isBatch = pathname === "/batch" || pathname.startsWith("/batch/");
  const isSchedule = pathname === "/schedule";
  const isRuns = pathname === "/runs" || pathname.startsWith("/runs/");
  const isAccounts = pathname === "/accounts";

  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}`} id="sidebar">
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Link href="/" className="brand-block" style={{ textDecoration: "none", flex: 1, minWidth: 0 }}>
          <div className="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <polygon points="8,6 19,12 8,18" fill="white" />
            </svg>
          </div>
          <div className="brand-text">
            <div className="brand-title">Content Engine</div>
            <div className="brand-subtitle">Upload once, publish everywhere</div>
          </div>
        </Link>
        <button
          type="button"
          className="sidebar-collapse-btn"
          id="sidebar-collapse-btn"
          title="Collapse sidebar"
          aria-label="Collapse sidebar"
          onClick={toggleCollapsed}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <polyline
              points="15,6 9,12 15,18"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <div>
        <div className="sidebar-section-label">Workspace</div>
        <nav className="sidebar-nav">
          <Link href="/" className={navClass(isUpload)} title="Upload & Drafts">
            <span className="nav-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 16V4M12 4l-4 4M12 4l4 4"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className="nav-label">Upload & Drafts</span>
          </Link>
          <Link href="/studio" className={navClass(isStudio)} title="Studio & Pipeline">
            <span className="nav-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="2" />
                <path d="M10 9l5 3-5 3V9z" fill="currentColor" />
              </svg>
            </span>
            <span className="nav-label">Studio & Pipeline</span>
            <span className="nav-badge">Live</span>
          </Link>
          <Link href="/batch" className={navClass(isBatch)} title="Batch Engine">
            <span className="nav-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M12 3l8 4.5-8 4.5-8-4.5L12 3z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                <path
                  d="M4 12l8 4.5 8-4.5M4 16.5L12 21l8-4.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className="nav-label">Batch Engine</span>
          </Link>
          <Link href="/schedule" className={navClass(isSchedule)} title="Schedule & Queue">
            <span className="nav-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="4" width="18" height="17" rx="2" stroke="currentColor" strokeWidth="2" />
                <path d="M3 9h18M8 2v4M16 2v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </span>
            <span className="nav-label">Schedule & Queue</span>
          </Link>
          <Link href="/runs" className={navClass(isRuns)} title="Runs & Library">
            <span className="nav-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </span>
            <span className="nav-label">Runs & Library</span>
            <span className="nav-count">{runsCount ?? 0}</span>
          </Link>
          <Link href="/accounts" className={navClass(isAccounts)} title="Connected Accounts">
            <span className="nav-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path
                  d="M10 14a5 5 0 0 0 7.07 0l2-2a5 5 0 0 0-7.07-7.07l-1 1"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M14 10a5 5 0 0 0-7.07 0l-2 2a5 5 0 0 0 7.07 7.07l1-1"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span className="nav-label">Connected Accounts</span>
          </Link>
        </nav>
      </div>

      <div>
        <div className="sidebar-section-label">Connected Channels</div>
        <div className="channel-list">
          {channels.map((ch) => (
            <div className="channel-row" key={ch.key}>
              <span className={`icon-badge ${ch.icon_class}`} style={{ width: 16, height: 16, fontSize: 8 }}>
                {ch.short}
              </span>
              {ch.label}
              <span
                className={`channel-status-dot ${ch.connected ? "connected" : "disconnected"}`}
                title={ch.connected ? "Connected" : "Not connected"}
              />
            </div>
          ))}
        </div>
      </div>

      {user && (
        <div style={{ marginTop: "auto" }}>
          {!collapsed && <div className="sidebar-section-label">Account</div>}
          <div
            style={{
              padding: "0 10px",
              display: "flex",
              flexDirection: collapsed ? "column" : "row",
              alignItems: collapsed ? "center" : "flex-start",
              justifyContent: "space-between",
              gap: 8,
              minWidth: 0,
            }}
          >
            {!collapsed && (
              <div style={{ minWidth: 0 }}>
                <div
                  className="brand-title"
                  style={{ fontSize: "0.8rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  title={user.email}
                >
                  {user.email}
                </div>
                <div className="brand-subtitle" style={{ textTransform: "capitalize" }}>
                  {user.role}
                </div>
              </div>
            )}
            <button
              type="button"
              className={collapsed ? "btn-icon" : "btn-secondary"}
              title={collapsed ? `Log out (${user.email})` : undefined}
              aria-label="Log out"
              onClick={handleLogout}
              style={collapsed ? undefined : { flexShrink: 0 }}
            >
              {collapsed ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <polyline points="16,17 21,12 16,7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              ) : (
                "Log out"
              )}
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
