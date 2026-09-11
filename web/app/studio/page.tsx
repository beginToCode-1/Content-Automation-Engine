"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { apiUrl } from "@/lib/api";

const STAGE_STEPS = [
  { key: "search", label: "Sourcing and Selecting Video" },
  { key: "download", label: "Downloading Source Media" },
  { key: "transcript", label: "Fetching Transcript" },
  { key: "segment", label: "Selecting Best Segment" },
  { key: "render", label: "Rendering 9:16 and Captions" },
  { key: "metadata", label: "Generating Metadata" },
  { key: "upload", label: "Publishing to Platforms" },
];

const CHECK_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
    <polyline points="4,12 9,17 20,6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const CROSS_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
    <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);
const CHEVRON_ICON = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ verticalAlign: "-1px" }}>
    <polyline points="9,5 16,12 9,19" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function stageIndexForKey(stageKey: string | null): number {
  if (!stageKey) return -1;
  const normalized = stageKey.startsWith("upload") ? "upload" : stageKey;
  return STAGE_STEPS.findIndex((s) => s.key === normalized);
}

interface RunEventLite {
  id: number;
}

export default function StudioPage() {
  const [topic, setTopic] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["youtube"]);
  const [mode, setMode] = useState("generate_and_upload");
  const [privacy, setPrivacy] = useState("private");
  const [statusText, setStatusText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [highestIdx, setHighestIdx] = useState(-1);
  const [runStatus, setRunStatus] = useState<"pending" | "running" | "succeeded" | "failed">("pending");
  const [monitorTitle, setMonitorTitle] = useState("Stage Monitor");
  const [idle, setIdle] = useState(true);
  const [previewNode, setPreviewNode] = useState<React.ReactNode>("No run in progress.");

  const sinceIdRef = useRef(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRunIdRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  function togglePlatform(value: string, checked: boolean) {
    setPlatforms((prev) => (checked ? [...prev, value] : prev.filter((p) => p !== value)));
  }

  function startPolling(runId: string, runTopic: string) {
    sinceIdRef.current = 0;
    activeRunIdRef.current = runId;
    setMonitorTitle("Tracking: " + runTopic);
    setIdle(false);
    setPreviewNode("Pipeline starting.");
    setHighestIdx(0);
    setRunStatus("running");

    async function poll() {
      if (activeRunIdRef.current !== runId) return;
      try {
        const res = await fetch(apiUrl(`/api/runs/${runId}?since_id=${sinceIdRef.current}`));
        if (res.ok) {
          const data = await res.json();
          for (const event of data.events as RunEventLite[]) {
            sinceIdRef.current = Math.max(sinceIdRef.current, event.id);
          }

          const idx = stageIndexForKey(data.run.current_stage);
          const effectiveIdx = idx === -1 ? 0 : idx;
          setHighestIdx(effectiveIdx);
          setRunStatus(data.run.status);

          if (data.run.status === "succeeded") {
            setPreviewNode(
              <>
                Run complete.{" "}
                <Link href={`/runs/${runId}`}>
                  View full run {CHEVRON_ICON}
                </Link>
              </>
            );
            setIdle(true);
            return;
          }
          if (data.run.status === "failed") {
            setPreviewNode(
              <>
                Run failed: {data.run.error_message || "see run detail"}.{" "}
                <Link href={`/runs/${runId}`}>
                  View full run {CHEVRON_ICON}
                </Link>
              </>
            );
            setIdle(true);
            return;
          }
          setPreviewNode("Rendering vertical short-form preview.");
        }
      } catch {
        // transient network error - keep polling
      }
      pollTimerRef.current = setTimeout(poll, 2000);
    }
    poll();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!platforms.length) {
      setStatusText("Select at least one platform.");
      return;
    }
    setStatusText("Starting.");
    setSubmitting(true);
    try {
      const response = await fetch(apiUrl("/api/runs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, mode, platforms, privacy }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setStatusText("Error: " + (err.detail || response.statusText));
        return;
      }
      const data = await response.json();
      setStatusText("");
      startPolling(data.run_id, topic);
    } catch (e) {
      setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        breadcrumb="Studio"
        title="Production Studio"
        subtitle="Search, clip, and auto-publish a new short from a topic across your connected platforms."
      />
      <div className="studio-grid">
        <div className="panel">
          <div className="panel-header">
            <h2>New Production Run</h2>
          </div>

          <form id="new-run-form" onSubmit={handleSubmit}>
            <div className="field">
              <label className="field-label" htmlFor="topic-input">
                Focus topic
              </label>
              <input
                type="text"
                id="topic-input"
                name="topic"
                placeholder="e.g. stoic philosophy, extreme sports, luxury watch history"
                required
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label">Target channels</label>
              <div className="toggle-row">
                <label className={`toggle-chip${platforms.includes("youtube") ? " checked" : ""}`} data-chip>
                  <input
                    type="checkbox"
                    name="platforms"
                    value="youtube"
                    checked={platforms.includes("youtube")}
                    onChange={(e) => togglePlatform("youtube", e.target.checked)}
                  />
                  <span className="icon-badge icon-yt">YT</span> YouTube Shorts
                </label>
                <label className={`toggle-chip${platforms.includes("instagram") ? " checked" : ""}`} data-chip>
                  <input
                    type="checkbox"
                    name="platforms"
                    value="instagram"
                    checked={platforms.includes("instagram")}
                    onChange={(e) => togglePlatform("instagram", e.target.checked)}
                  />
                  <span className="icon-badge icon-ig">IG</span> Instagram Reels
                </label>
                <label className={`toggle-chip${platforms.includes("tiktok") ? " checked" : ""}`} data-chip>
                  <input
                    type="checkbox"
                    name="platforms"
                    value="tiktok"
                    checked={platforms.includes("tiktok")}
                    onChange={(e) => togglePlatform("tiktok", e.target.checked)}
                  />
                  <span className="icon-badge icon-tt">TT</span> TikTok
                </label>
              </div>
            </div>

            <div className="field">
              <label className="field-label">Execution mode</label>
              <div className="segmented">
                <input
                  type="radio"
                  name="mode"
                  value="generate_and_upload"
                  id="mode-upload"
                  checked={mode === "generate_and_upload"}
                  onChange={() => setMode("generate_and_upload")}
                />
                <label htmlFor="mode-upload">Generate and Publish</label>
                <input
                  type="radio"
                  name="mode"
                  value="generate_only"
                  id="mode-dry"
                  checked={mode === "generate_only"}
                  onChange={() => setMode("generate_only")}
                />
                <label htmlFor="mode-dry">Dry Run (Draft Only)</label>
              </div>
            </div>

            <div className="field">
              <label className="field-label">Upload privacy</label>
              <div className="segmented">
                <input
                  type="radio"
                  name="privacy"
                  value="private"
                  id="run-privacy-private"
                  checked={privacy === "private"}
                  onChange={() => setPrivacy("private")}
                />
                <label htmlFor="run-privacy-private">Private</label>
                <input
                  type="radio"
                  name="privacy"
                  value="public"
                  id="run-privacy-public"
                  checked={privacy === "public"}
                  onChange={() => setPrivacy("public")}
                />
                <label htmlFor="run-privacy-public">Public</label>
              </div>
              <div className="field-hint">Public goes live immediately once the run finishes uploading.</div>
            </div>

            <button type="submit" className="btn-run" disabled={submitting}>
              <span className="btn-run-inner" id="run-btn-inner">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <polygon points="6,4 20,12 6,20" fill="currentColor" />
                </svg>
                Start Run
              </span>
            </button>
            <div id="new-run-status" className="status-text">
              {statusText}
            </div>
          </form>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2 id="monitor-title">{monitorTitle}</h2>
            <span className={`live-dot${idle ? " idle" : ""}`} id="live-dot" />
          </div>

          <div className="stage-list" id="stage-list">
            {STAGE_STEPS.map((step, i) => {
              let stateClass = "pending";
              let icon: React.ReactNode = <span className="stage-dot" />;
              if (i < highestIdx) {
                stateClass = "done";
                icon = <span className="stage-check">{CHECK_ICON}</span>;
              } else if (i === highestIdx) {
                if (runStatus === "failed") {
                  stateClass = "failed";
                  icon = <span style={{ color: "var(--danger)" }}>{CROSS_ICON}</span>;
                } else if (runStatus === "succeeded") {
                  stateClass = "done";
                  icon = <span className="stage-check">{CHECK_ICON}</span>;
                } else {
                  stateClass = "active";
                }
              }
              return (
                <div className={`stage-row ${stateClass}`} key={step.key}>
                  <div className="stage-row-left">
                    <span className="stage-num">0{i + 1}</span>
                    <span className="stage-title">{step.label}</span>
                  </div>
                  {icon}
                </div>
              );
            })}
          </div>

          <div className="preview-box">
            <div className="preview-box-label">Status</div>
            <div className="preview-box-text" id="preview-text">
              {previewNode}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
