"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/PageHeader";
import RelativeTime from "@/components/RelativeTime";
import { apiFetch, platformsFromStr, type Batch, type MetaResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Fallback values used only until /api/meta's batch_defaults resolves (mirrors
// config.py's own env-var defaults: BATCH_MAX_VIDEOS=5, BATCH_MAX_CLIPS_PER_VIDEO=5,
// BATCH_DEFAULT_STAGGER_MINUTES=180), so the form isn't empty during that brief load.
const FALLBACK_MAX_VIDEOS = 5;
const FALLBACK_MAX_CLIPS_PER_VIDEO = 5;
const FALLBACK_DEFAULT_STAGGER_MINUTES = 180;

function formatOffset(totalMinutes: number): string {
  if (totalMinutes < 60) return "+" + totalMinutes + "m";
  const hours = totalMinutes / 60;
  return "+" + (Number.isInteger(hours) ? hours : hours.toFixed(1)) + "h";
}

export default function BatchPage() {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [topic, setTopic] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["youtube"]);
  const [videosCount, setVideosCount] = useState(2);
  const [clipsPerVideo, setClipsPerVideo] = useState(3);
  const [staggerMinutes, setStaggerMinutes] = useState(FALLBACK_DEFAULT_STAGGER_MINUTES);
  const [privacy, setPrivacy] = useState("private");
  const [statusText, setStatusText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [maxVideos, setMaxVideos] = useState(FALLBACK_MAX_VIDEOS);
  const [maxClipsPerVideo, setMaxClipsPerVideo] = useState(FALLBACK_MAX_CLIPS_PER_VIDEO);

  const [batches, setBatches] = useState<Batch[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiFetch<MetaResponse>("/api/meta")
      .then((data) => {
        if (cancelled) return;
        setMaxVideos(data.batch_defaults.max_videos);
        setMaxClipsPerVideo(data.batch_defaults.max_clips_per_video);
        setStaggerMinutes(data.batch_defaults.default_stagger_minutes);
      })
      .catch(() => {
        // Form falls back to the hardcoded defaults if the backend isn't reachable yet.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ batches: Batch[] }>("/api/batches?limit=20")
      .then((data) => {
        if (!cancelled) setBatches(data.batches);
      })
      .finally(() => {
        if (!cancelled) setLoadingBatches(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function togglePlatform(value: string, checked: boolean) {
    setPlatforms((prev) => (checked ? [...prev, value] : prev.filter((p) => p !== value)));
  }

  const totalClips = Math.max(1, videosCount || 1) * Math.max(1, clipsPerVideo || 1);
  const stagger = Math.max(1, staggerMinutes || 1);

  const timelineBadges = useMemo(() => {
    const maxBadges = 8;
    const shown = Math.min(totalClips, maxBadges);
    const badges: string[] = [];
    for (let i = 1; i <= shown; i++) {
      badges.push(formatOffset(i * stagger));
    }
    const more = totalClips > maxBadges ? totalClips - maxBadges : 0;
    return { badges, more };
  }, [totalClips, stagger]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!platforms.length) {
      setStatusText("Select at least one platform.");
      return;
    }
    setStatusText("Starting.");
    setSubmitting(true);
    try {
      const data = await apiFetch<{ batch_id: string }>("/api/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          platforms,
          videos_count: videosCount,
          clips_per_video: clipsPerVideo,
          stagger_gap_minutes: staggerMinutes,
          privacy,
        }),
      });
      router.push(`/batch/${data.batch_id}`);
    } catch (e) {
      setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        breadcrumb="Batch"
        title="Batch Engine"
        subtitle="Slice one topic into multiple clips across videos, with staggered multi-channel publication."
      />

      <div className="info-banner">
        <span className="info-banner-icon">i</span>
        <span className="info-banner-text">
          Each clip is generated up front, then queued for upload at a staggered time. You can review or cancel any
          individual clip&apos;s scheduled upload from its own run page before it fires.
        </span>
      </div>

      {!isAdmin && (
        <p className="note" style={{ marginBottom: 20 }}>
          Admin access required to start a batch. You can still review batches and their clips below.
        </p>
      )}

      <div className="panel form-panel">
        <div className="panel-header">
          <h2>New Batch Run</h2>
        </div>

        <form id="new-batch-form" onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label" htmlFor="batch-topic">
              Focus topic
            </label>
            <input
              type="text"
              id="batch-topic"
              name="topic"
              placeholder="e.g. stoic philosophy"
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
                <span className="icon-badge icon-yt">YT</span> YouTube
              </label>
              <label className={`toggle-chip${platforms.includes("instagram") ? " checked" : ""}`} data-chip>
                <input
                  type="checkbox"
                  name="platforms"
                  value="instagram"
                  checked={platforms.includes("instagram")}
                  onChange={(e) => togglePlatform("instagram", e.target.checked)}
                />
                <span className="icon-badge icon-ig">IG</span> Instagram
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
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <label className="field-label" htmlFor="batch-videos-count" style={{ marginBottom: 0 }}>
                Source videos
              </label>
              <span className="yield-indicator" id="batch-yield-indicator">
                Yield: {totalClips} Scheduled Short{totalClips === 1 ? "" : "s"}
              </span>
            </div>
            <input
              type="number"
              id="batch-videos-count"
              name="videos_count"
              value={videosCount}
              min={1}
              max={maxVideos}
              required
              style={{ marginTop: 8 }}
              onChange={(e) => setVideosCount(parseInt(e.target.value, 10) || 1)}
            />
            <div className="field-hint">Up to {maxVideos} different source videos for this topic.</div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="batch-clips-per-video">
              Clips per video
            </label>
            <input
              type="number"
              id="batch-clips-per-video"
              name="clips_per_video"
              value={clipsPerVideo}
              min={1}
              max={maxClipsPerVideo}
              required
              onChange={(e) => setClipsPerVideo(parseInt(e.target.value, 10) || 1)}
            />
            <div className="field-hint">Up to {maxClipsPerVideo} non-overlapping clips extracted from each video.</div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="batch-stagger">
              Time between uploads (minutes)
            </label>
            <input
              type="number"
              id="batch-stagger"
              name="stagger_gap_minutes"
              value={staggerMinutes}
              min={1}
              required
              onChange={(e) => setStaggerMinutes(parseInt(e.target.value, 10) || 1)}
            />
            <div className="field-hint">
              Each clip uploads this many minutes after the previous one, so they don&apos;t all post at once.
            </div>
            <div className="stagger-timeline" id="batch-stagger-timeline">
              {timelineBadges.badges.map((b, i) => (
                <span className="stagger-badge" key={i}>
                  {b}
                </span>
              ))}
              {timelineBadges.more > 0 && <span className="stagger-badge">+{timelineBadges.more} more</span>}
            </div>
          </div>

          <div className="field">
            <label className="field-label">Upload privacy</label>
            <div className="segmented">
              <input
                type="radio"
                name="privacy"
                value="private"
                id="batch-privacy-private"
                checked={privacy === "private"}
                onChange={() => setPrivacy("private")}
              />
              <label htmlFor="batch-privacy-private">Private</label>
              <input
                type="radio"
                name="privacy"
                value="public"
                id="batch-privacy-public"
                checked={privacy === "public"}
                onChange={() => setPrivacy("public")}
              />
              <label htmlFor="batch-privacy-public">Public</label>
            </div>
            <div className="field-hint">
              Batch uploads use this setting exactly as chosen - a public choice will actually go live automatically
              once its scheduled time arrives, even if you are away.
            </div>
          </div>

          <button
            type="submit"
            className="btn-run"
            disabled={submitting || !isAdmin}
            title={isAdmin ? undefined : "Admin access required"}
          >
            <span className="btn-run-inner">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <polygon points="6,4 20,12 6,20" fill="currentColor" />
              </svg>
              Start Batch
            </span>
          </button>
          <div id="new-batch-status" className="status-text">
            {statusText}
          </div>
        </form>
      </div>

      <h1 className="section-title">Recent Batches</h1>
      <div className="panel">
        <div className="table-scroll">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Status</th>
                <th>Videos</th>
                <th>Clips/Video</th>
                <th>Platforms</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {!loadingBatches && batches.length === 0 && (
                <tr>
                  <td colSpan={6}>No batches yet. Start one above.</td>
                </tr>
              )}
              {batches.map((batch) => (
                <tr key={batch.batch_id}>
                  <td>
                    <Link href={`/batch/${batch.batch_id}`}>{batch.topic}</Link>
                  </td>
                  <td>
                    <span className={`badge badge-${batch.status === "running" ? "running" : batch.status}`}>
                      {batch.status}
                    </span>
                  </td>
                  <td>{batch.videos_count}</td>
                  <td>{batch.clips_per_video}</td>
                  <td>{(batch.platforms ?? platformsFromStr(batch.target_platforms)).join(", ")}</td>
                  <td>
                    <RelativeTime value={batch.created_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
