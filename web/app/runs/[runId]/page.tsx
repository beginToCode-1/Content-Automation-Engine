"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { apiFetch, mediaUrl, platformsFromStr, type Run, type RunDetailResponse, type RunEvent, type Upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RunDetailPage() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const sinceIdRef = useRef(0);
  const lastStatusRef = useRef<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await apiFetch<RunDetailResponse>(`/api/runs/${runId}`);
        if (cancelled) return;
        setRun(data.run);
        setEvents(data.events);
        setUploads(data.uploads);
        sinceIdRef.current = data.events.reduce((max, e) => Math.max(max, e.id), 0);
        lastStatusRef.current = data.run.status;
        setLoading(false);
        if (data.run.status === "pending" || data.run.status === "running") {
          pollTimerRef.current = setTimeout(poll, 2000);
        }
      } catch {
        if (!cancelled) {
          setNotFound(true);
          setLoading(false);
        }
      }
    }

    async function poll() {
      try {
        const data = await apiFetch<RunDetailResponse>(`/api/runs/${runId}?since_id=${sinceIdRef.current}`);
        if (!cancelled) {
          setRun(data.run);
          if (data.events.length) {
            setEvents((prev) => [...prev, ...data.events]);
            sinceIdRef.current = data.events.reduce((max, e) => Math.max(max, e.id), sinceIdRef.current);
          }

          if (
            data.run.status !== lastStatusRef.current &&
            (data.run.status === "succeeded" || data.run.status === "failed")
          ) {
            // The original reloads the whole page here (window.location.reload())
            // so every server-rendered field picks up its final value. We port
            // that as a full refetch of run+events+uploads instead of a hard
            // reload, since this page has no server-rendered HTML to refresh.
            const fresh = await apiFetch<RunDetailResponse>(`/api/runs/${runId}`);
            if (!cancelled) {
              setRun(fresh.run);
              setEvents(fresh.events);
              setUploads(fresh.uploads);
            }
            lastStatusRef.current = data.run.status;
            return;
          }
          lastStatusRef.current = data.run.status;
        }
      } catch {
        // transient network error - keep polling
      }
      if (!cancelled && (lastStatusRef.current === "pending" || lastStatusRef.current === "running")) {
        pollTimerRef.current = setTimeout(poll, 2000);
      }
    }

    load();
    return () => {
      cancelled = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [runId]);

  async function handleCancelUpload() {
    setCancelling(true);
    try {
      await apiFetch(`/api/runs/${runId}/cancel-upload`, { method: "POST" });
      const fresh = await apiFetch<RunDetailResponse>(`/api/runs/${runId}`);
      setRun(fresh.run);
      setEvents(fresh.events);
      setUploads(fresh.uploads);
    } catch {
      // matches the previous behavior: a failed cancel just leaves the run as-is
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return (
      <>
        <PageHeader breadcrumb="Runs" title="Loading..." />
      </>
    );
  }

  if (notFound || !run) {
    return (
      <>
        <PageHeader breadcrumb="Runs" title="Run not found" />
        <p className="error">Run not found.</p>
      </>
    );
  }

  const platforms = platformsFromStr(run.target_platforms);
  const queued = run.status === "succeeded" && !!run.scheduled_upload_at;
  const headerAction =
    run.source_type === "own_upload" ? (
      <Link href="/" className="btn-header-action">
        Back to Upload
      </Link>
    ) : (
      <Link href="/studio" className="btn-header-action">
        Back to Studio
      </Link>
    );

  return (
    <>
      <PageHeader breadcrumb="Runs" title={run.topic} action={headerAction} />

      <p className="meta-line" style={{ marginBottom: 20, marginTop: -14 }}>
        {queued ? (
          <span className="badge badge-queued" id="run-status">
            queued
          </span>
        ) : (
          <span className={`badge badge-${run.status}`} id="run-status">
            {run.status}
          </span>
        )}
        {" · Stage: "}
        <strong id="run-stage" style={{ color: "var(--text)" }}>
          {run.current_stage || "-"}
        </strong>
        {" · Trigger: " + run.trigger_source}
        {" · Platforms: " + platforms.join(", ")}
      </p>

      {run.error_message && <p className="error">{run.error_message}</p>}

      {run.scheduled_upload_at && (
        <p className="note">
          Upload scheduled for {run.scheduled_upload_at}.
          {isAdmin && (
            <button
              type="button"
              className="btn-secondary"
              style={{ marginLeft: 10 }}
              disabled={cancelling}
              onClick={handleCancelUpload}
            >
              Cancel scheduled upload
            </button>
          )}
        </p>
      )}

      <div className="studio-grid">
        <div className="panel">
          {run.clip_path ? (
            <video controls src={mediaUrl(run.run_id)} />
          ) : (
            <div className="preview-box">
              <div className="preview-box-text">No clip rendered for this run.</div>
            </div>
          )}

          {run.metadata_title && (
            <>
              <h2 style={{ marginTop: 18 }}>Generated Metadata</h2>
              <p style={{ fontWeight: 600, margin: "8px 0 4px" }}>{run.metadata_title}</p>
              <p className="meta-line">{run.metadata_description}</p>
            </>
          )}
        </div>

        <div className="panel">
          <h2 style={{ marginBottom: 12 }}>Uploads</h2>
          <ul id="upload-list">
            {uploads.length === 0 && <li>No upload attempts yet.</li>}
            {uploads.map((upload, i) => (
              <li key={i}>
                {upload.platform}: {upload.status}
                {upload.url && (
                  <>
                    {" - "}
                    <a href={upload.url} target="_blank" rel="noreferrer">
                      {upload.url}
                    </a>
                  </>
                )}
                {upload.error_message && <> - {upload.error_message}</>}
              </li>
            ))}
          </ul>

          <h2 style={{ margin: "18px 0 12px" }}>Progress Log</h2>
          <ul id="event-list">
            {events.length === 0 && <li>Waiting for the run to start.</li>}
            {events.map((event) => (
              <li key={event.id}>
                [{event.stage}] {event.message}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
