"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  apiFetch,
  mediaUrl,
  type Run,
  type RunDetailResponse,
  type Upload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Shared, reusable port of static/modals.js's three modals (clip preview,
// metadata inspector, failure diagnostics with retry+poll). Exposes
// imperative openers plus the JSX to render once, at the bottom of any page
// that needs them (runs library today - see openDiagnostic's onResolved for
// how the library page refreshes its row after a retry finishes).
type ModalState =
  | { kind: "closed" }
  | { kind: "loading"; title: string }
  | { kind: "load-error" }
  | { kind: "preview"; run: Run; uploads: Upload[] }
  | { kind: "metadata-empty" }
  | { kind: "metadata"; run: Run }
  | { kind: "diagnostic"; run: Run };

async function fetchRun(runId: string): Promise<RunDetailResponse> {
  try {
    return await apiFetch<RunDetailResponse>(`/api/runs/${runId}`);
  } catch {
    throw new Error("Run not found");
  }
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // clipboard API unavailable/blocked - silently ignore, matching the original
    }
  }
  return (
    <div className="copy-field">
      <div className="field-label">{label}</div>
      <div className="copy-field-row">
        <div className="copy-field-value">{value}</div>
        <button
          type="button"
          className={`copy-btn${copied ? " copied" : ""}`}
          title="Copy"
          onClick={handleCopy}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <rect x="9" y="9" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="2" />
            <path d="M5 15V5a2 2 0 0 1 2-2h10" stroke="currentColor" strokeWidth="2" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export function useRunModals() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [state, setState] = useState<ModalState>({ kind: "closed" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onResolvedRef = useRef<((run: Run) => void) | null>(null);

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const closeModal = useCallback(() => {
    clearPoll();
    onResolvedRef.current = null;
    setState({ kind: "closed" });
  }, [clearPoll]);

  useEffect(() => {
    function onKeydown(e: KeyboardEvent) {
      if (e.key === "Escape") closeModal();
    }
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, [closeModal]);

  useEffect(() => () => clearPoll(), [clearPoll]);

  const openClipPreview = useCallback(async (runId: string) => {
    setState({ kind: "loading", title: "Loading..." });
    try {
      const data = await fetchRun(runId);
      setState({ kind: "preview", run: data.run, uploads: data.uploads });
    } catch {
      setState({ kind: "load-error" });
    }
  }, []);

  const openMetadataInspector = useCallback(async (runId: string) => {
    setState({ kind: "loading", title: "Loading..." });
    try {
      const data = await fetchRun(runId);
      if (!data.run.metadata_title) {
        setState({ kind: "metadata-empty" });
      } else {
        setState({ kind: "metadata", run: data.run });
      }
    } catch {
      setState({ kind: "load-error" });
    }
  }, []);

  const openDiagnostic = useCallback(async (runId: string, onResolved?: (run: Run) => void) => {
    onResolvedRef.current = onResolved || null;
    setState({ kind: "loading", title: "Loading..." });
    try {
      const data = await fetchRun(runId);
      setState({ kind: "diagnostic", run: data.run });
    } catch {
      setState({ kind: "load-error" });
    }
  }, []);

  const retryPollingRunId = useRef<string | null>(null);
  const [retryStatus, setRetryStatus] = useState("");
  const [retrying, setRetrying] = useState(false);

  const retryRun = useCallback(
    async (runId: string) => {
      setRetrying(true);
      setRetryStatus("Retrying...");
      try {
        const body = await apiFetch<{ run_id: string }>(`/api/runs/${runId}/retry`, { method: "POST" });
        const pollId = body.run_id;
        retryPollingRunId.current = pollId;
        setRetryStatus("Retrying - watching for a result...");
        clearPoll();
        pollRef.current = setInterval(async () => {
          try {
            const check = await fetchRun(pollId);
            if (check.run.status === "succeeded" || check.run.status === "failed") {
              clearPoll();
              setState({ kind: "diagnostic", run: check.run });
              setRetrying(false);
              setRetryStatus("");
              if (onResolvedRef.current) onResolvedRef.current(check.run);
            }
          } catch {
            // transient network error - keep polling
          }
        }, 2000);
      } catch (e) {
        const message = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
        setRetryStatus("Retry failed: " + message);
        setRetrying(false);
      }
    },
    [clearPoll]
  );

  let dialog: React.ReactNode = null;
  if (state.kind !== "closed") {
    let title = "";
    let body: React.ReactNode = null;
    let wide = false;

    if (state.kind === "loading") {
      title = state.title;
      body = <div className="modal-body">Loading...</div>;
    } else if (state.kind === "load-error") {
      title = "Error";
      body = <div className="modal-body">Could not load this run.</div>;
    } else if (state.kind === "preview") {
      const { run, uploads } = state;
      wide = true;
      title = run.topic;
      const hasClip = !!run.clip_path;
      body = (
        <div className="modal-body">
          <div className="modal-split">
            <div>
              {hasClip ? (
                <div className="phone-frame">
                  <video controls src={mediaUrl(run.run_id)} />
                </div>
              ) : (
                <div className="preview-box">
                  <div className="preview-box-text">No clip rendered for this run.</div>
                </div>
              )}
              {hasClip && (
                <a
                  href={mediaUrl(run.run_id)}
                  className="btn-secondary"
                  style={{ display: "block", textAlign: "center", marginTop: 14 }}
                  download
                >
                  Download Master MP4
                </a>
              )}
            </div>
            <div>
              <h2 style={{ marginBottom: 10 }}>{run.metadata_title || run.topic}</h2>
              <p className="meta-line" style={{ marginBottom: 18 }}>
                {run.metadata_description || ""}
              </p>
              <h2 style={{ marginBottom: 10, fontSize: "0.9rem" }}>Uploads</h2>
              {uploads.length ? (
                uploads.map((u, i) => (
                  <div className="copy-field" key={i}>
                    <div className="field-label">{u.platform}</div>
                    {u.url ? (
                      <a href={u.url} target="_blank" rel="noreferrer" className="copy-field-value" style={{ display: "block" }}>
                        {u.url}
                      </a>
                    ) : (
                      <div className="copy-field-value">{u.status}</div>
                    )}
                  </div>
                ))
              ) : (
                <p className="meta-line">No upload attempts yet.</p>
              )}
            </div>
          </div>
        </div>
      );
    } else if (state.kind === "metadata-empty") {
      title = "Metadata";
      body = (
        <div className="modal-body">
          <p className="meta-line">No metadata has been generated for this run yet.</p>
        </div>
      );
    } else if (state.kind === "metadata") {
      const { run } = state;
      title = "Metadata Inspector";
      let hashtags: string[] = [];
      try {
        hashtags = run.metadata_hashtags ? JSON.parse(run.metadata_hashtags) : [];
      } catch {
        hashtags = [];
      }
      const hashtagText = hashtags.map((h) => "#" + h).join(" ");
      const allText = [run.metadata_title, run.metadata_description, hashtagText].filter(Boolean).join("\n\n");
      body = (
        <div className="modal-body">
          <CopyField label="Title" value={run.metadata_title || ""} />
          <CopyField label="Description" value={run.metadata_description || ""} />
          <CopyField label="Hashtags" value={hashtagText} />
          <CopyAllButton text={allText} />
        </div>
      );
    } else if (state.kind === "diagnostic") {
      const { run } = state;
      title = "Diagnostics - " + run.topic;
      body = (
        <div className="modal-body">
          <div className="diagnostic-status-row">
            <span className={`badge badge-${run.status}`}>{run.status}</span>
            <span className="meta-line">Stage: {run.current_stage || "-"}</span>
          </div>
          {run.error_message ? (
            <div className="diagnostic-error">{run.error_message}</div>
          ) : (
            <p className="meta-line" style={{ marginBottom: 18 }}>
              No error recorded.
            </p>
          )}
          {run.status === "failed" && isAdmin && (
            <>
              <button
                type="button"
                className="btn-run"
                disabled={retrying}
                onClick={() => retryRun(run.run_id)}
              >
                <span className="btn-run-inner">Retry Pipeline Now</span>
              </button>
              <div className="status-text" style={{ marginLeft: 0, marginTop: 8 }}>
                {retryStatus}
              </div>
            </>
          )}
          {run.status === "failed" && !isAdmin && (
            <p className="field-hint">Admin access required to retry a failed run.</p>
          )}
        </div>
      );
    }

    dialog = (
      <div className="modal-backdrop open" onClick={(e) => { if (e.target === e.currentTarget) closeModal(); }}>
        <div className={`modal-dialog${wide ? " modal-wide" : ""}`}>
          <div className="modal-header">
            <span className="modal-title">{title}</span>
            <button type="button" className="modal-close" aria-label="Close" onClick={closeModal}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          {body}
        </div>
      </div>
    );
  }

  return { openClipPreview, openMetadataInspector, openDiagnostic, closeModal, modal: dialog };
}

function CopyAllButton({ text }: { text: string }) {
  const [label, setLabel] = useState("Copy All for Upload");
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setLabel("Copied!");
      setTimeout(() => setLabel("Copy All for Upload"), 1200);
    } catch {
      // ignore
    }
  }
  return (
    <button type="button" className="btn-run" style={{ marginTop: 6 }} onClick={handleCopy}>
      <span className="btn-run-inner">{label}</span>
    </button>
  );
}
