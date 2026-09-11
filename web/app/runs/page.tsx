"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/PageHeader";
import RelativeTime from "@/components/RelativeTime";
import { useRunModals } from "@/components/modals/useRunModals";
import { apiFetch, platformsFromStr, type Run, type RunsListResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RunsLibraryPage() {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [platformFilter, setPlatformFilter] = useState("");
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const { openClipPreview, openMetadataInspector, openDiagnostic, modal } = useRunModals();

  useEffect(() => {
    let cancelled = false;
    apiFetch<RunsListResponse>("/api/runs?limit=200")
      .then((data) => {
        if (!cancelled) setRuns(data.runs);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function updateRunInPlace(updated: Run) {
    setRuns((prev) => prev.map((r) => (r.run_id === updated.run_id ? { ...r, ...updated } : r)));
  }

  const succeededCount = useMemo(() => runs.filter((r) => r.status === "succeeded").length, [runs]);
  const failedCount = useMemo(() => runs.filter((r) => r.status === "failed").length, [runs]);

  const visibleRuns = useMemo(() => {
    const query = search.trim().toLowerCase();
    return runs.filter((run) => {
      const matchesStatus = statusFilter === "all" || run.status === statusFilter;
      const platforms = platformsFromStr(run.target_platforms);
      const matchesPlatform = !platformFilter || platforms.includes(platformFilter);
      const searchText = (run.topic + " " + (run.metadata_title || "")).toLowerCase();
      const matchesSearch = !query || searchText.includes(query);
      return matchesStatus && matchesPlatform && matchesSearch;
    });
  }, [runs, search, statusFilter, platformFilter]);

  async function handleRetry(runId: string) {
    setRetryingId(runId);
    try {
      const data = await apiFetch<{ run_id: string }>(`/api/runs/${runId}/retry`, { method: "POST" });
      router.push(`/runs/${data.run_id}`);
    } catch (e) {
      alert("Retry failed: " + (e instanceof Error ? e.message : String(e)));
      setRetryingId(null);
    }
  }

  return (
    <>
      <PageHeader
        breadcrumb="Runs"
        title="Runs & Library"
        subtitle="Every run across Studio, Batch, and Upload - search, filter, and retry failed jobs."
      />

      <div className="library-toolbar">
        <div className="search-input-wrap">
          <span className="search-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <input
            type="text"
            id="library-search"
            placeholder="Search runs by topic or title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-tabs" id="status-filter-tabs">
          <button type="button" className={statusFilter === "all" ? "active" : ""} onClick={() => setStatusFilter("all")}>
            All ({runs.length})
          </button>
          <button
            type="button"
            className={statusFilter === "succeeded" ? "active" : ""}
            onClick={() => setStatusFilter("succeeded")}
          >
            Succeeded ({succeededCount})
          </button>
          <button
            type="button"
            className={statusFilter === "failed" ? "active" : ""}
            onClick={() => setStatusFilter("failed")}
          >
            Failed ({failedCount})
          </button>
        </div>
        <select
          className="platform-select"
          id="platform-filter"
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        >
          <option value="">All Platforms</option>
          <option value="youtube">YouTube</option>
          <option value="instagram">Instagram</option>
          <option value="tiktok">TikTok</option>
        </select>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Recent Runs</h2>
          <span className="status-pill" id="library-count-label">
            Showing {loading ? 0 : visibleRuns.length} of {runs.length} runs
          </span>
        </div>
        <div className="table-scroll">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Video & Topic</th>
                <th>Status</th>
                <th>Stage</th>
                <th>Platforms</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="library-rows">
              {!loading && visibleRuns.length === 0 && (
                <tr>
                  <td colSpan={6}>No runs yet.</td>
                </tr>
              )}
              {visibleRuns.map((run) => {
                const platforms = platformsFromStr(run.target_platforms);
                const queued = run.status === "succeeded" && run.scheduled_upload_at;
                return (
                  <tr key={run.run_id}>
                    <td>
                      <Link href={`/runs/${run.run_id}`}>{run.topic}</Link>
                      {run.metadata_title && run.metadata_title !== run.topic && (
                        <span className="run-title-sub">{run.metadata_title}</span>
                      )}
                    </td>
                    <td>
                      {queued ? (
                        <span className="badge badge-queued">queued</span>
                      ) : run.status === "failed" ? (
                        <span
                          className="badge badge-failed diagnostic-trigger"
                          style={{ cursor: "pointer" }}
                          title="Click for diagnostics"
                          onClick={() => openDiagnostic(run.run_id, updateRunInPlace)}
                        >
                          failed
                        </span>
                      ) : (
                        <span className={`badge badge-${run.status}`}>{run.status}</span>
                      )}
                    </td>
                    <td>{run.current_stage || "-"}</td>
                    <td>{platforms.join(", ")}</td>
                    <td>
                      <RelativeTime value={run.created_at} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          type="button"
                          className="btn-icon preview-trigger"
                          title="Play preview"
                          onClick={() => openClipPreview(run.run_id)}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"
                              stroke="currentColor"
                              strokeWidth="2"
                            />
                            <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="btn-icon metadata-trigger"
                          title="Inspect metadata"
                          onClick={() => openMetadataInspector(run.run_id)}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <path
                              d="M6 2h9l5 5v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinejoin="round"
                            />
                            <path d="M9 13h6M9 17h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                          </svg>
                        </button>
                        {run.status === "failed" && isAdmin && (
                          <button
                            type="button"
                            className="btn-secondary btn-retry retry-btn"
                            disabled={retryingId === run.run_id}
                            onClick={() => handleRetry(run.run_id)}
                          >
                            {retryingId === run.run_id ? "Retrying..." : "Retry"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {modal}
    </>
  );
}
