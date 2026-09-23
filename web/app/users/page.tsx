"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import PageHeader from "@/components/PageHeader";
import RelativeTime from "@/components/RelativeTime";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface AdminUser {
  id: string;
  email: string;
  role: "admin" | "viewer";
  created_at: string;
}

export default function UsersPage() {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusText, setStatusText] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  // This app has no server-side route protection anywhere - the backend's
  // 403 on /api/users is the real gate. This just avoids showing a viewer
  // an empty/broken admin page instead of redirecting them away from it.
  useEffect(() => {
    if (user && !isAdmin) {
      router.replace("/");
    }
  }, [user, isAdmin, router]);

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    apiFetch<AdminUser[]>("/api/users")
      .then((data) => {
        if (!cancelled) setUsers(data);
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
  }, [isAdmin]);

  async function handleRoleChange(target: AdminUser, role: "admin" | "viewer") {
    setUpdatingId(target.id);
    setStatusText("");
    try {
      const updated = await apiFetch<AdminUser>(`/api/users/${target.id}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e) {
      setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setUpdatingId(null);
    }
  }

  if (!isAdmin) {
    return (
      <>
        <PageHeader breadcrumb="Users" title="Users" action={null} />
        <p className="meta-line">Admin access required.</p>
      </>
    );
  }

  return (
    <>
      <PageHeader
        breadcrumb="Users"
        title="Users"
        subtitle="Promote or demote accounts on this deployment."
        action={null}
      />

      <p className="note" style={{ marginBottom: 20 }}>
        A role change takes effect the next time that person logs in - it isn&apos;t applied to a
        session that&apos;s already signed in.
      </p>

      <div className="panel form-panel">
        <div className="panel-header">
          <h2>All Users</h2>
        </div>

        {loading && <p className="meta-line">Loading...</p>}
        {!loading && users.length === 0 && <p className="meta-line">No users found.</p>}

        {!loading && users.length > 0 && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {users.map((row) => {
              const isSelf = row.id === user?.id;
              const nextRole = row.role === "admin" ? "viewer" : "admin";
              return (
                <li
                  key={row.id}
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
                    <div style={{ fontWeight: 500 }}>
                      {row.email}
                      {isSelf && <span className="meta-line"> (you)</span>}
                    </div>
                    <div className="meta-line" style={{ fontSize: "0.78rem", marginTop: 2 }}>
                      <span style={{ textTransform: "capitalize" }}>{row.role}</span>
                      {" · Joined "}
                      <RelativeTime value={row.created_at} />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={isSelf || updatingId === row.id}
                    title={isSelf ? "You cannot change your own role" : undefined}
                    onClick={() => handleRoleChange(row, nextRole)}
                    style={{ flexShrink: 0, textTransform: "capitalize" }}
                  >
                    Make {nextRole}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {statusText && <div className="status-text" style={{ marginLeft: 0, marginTop: 10 }}>{statusText}</div>}
      </div>
    </>
  );
}
