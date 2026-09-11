"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { apiFetch, platformsFromStr, type Batch, type BatchClip, type BatchDetailResponse } from "@/lib/api";

export default function BatchDetailPage() {
  const params = useParams<{ batchId: string }>();
  const batchId = params.batchId;

  const [batch, setBatch] = useState<Batch | null>(null);
  const [clips, setClips] = useState<BatchClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await apiFetch<BatchDetailResponse>(`/api/batches/${batchId}`);
        if (cancelled) return;
        setBatch(data.batch);
        if (data.clips.length) setClips(data.clips);
        if (data.batch.status !== "running") {
          return;
        }
      } catch {
        // transient network error - keep polling
      }
      if (!cancelled) pollTimerRef.current = setTimeout(poll, 3000);
    }

    async function load() {
      try {
        const data = await apiFetch<BatchDetailResponse>(`/api/batches/${batchId}`);
        if (cancelled) return;
        setBatch(data.batch);
        setClips(data.clips);
        setLoading(false);
        poll();
      } catch {
        if (!cancelled) {
          setNotFound(true);
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [batchId]);

  if (loading) {
    return <PageHeader breadcrumb="Batch" title="Loading..." />;
  }

  if (notFound || !batch) {
    return (
      <>
        <PageHeader breadcrumb="Batch" title="Batch not found" />
        <p className="error">Batch not found.</p>
      </>
    );
  }

  const platforms = platformsFromStr(batch.target_platforms);

  return (
    <>
      <PageHeader
        breadcrumb="Batch"
        title={batch.topic}
        action={
          <Link href="/batch" className="btn-header-action">
            Back to Batches
          </Link>
        }
      />

      <p className="meta-line" style={{ marginBottom: 20, marginTop: -14 }}>
        <span className={`badge badge-${batch.status === "running" ? "running" : batch.status}`} id="batch-status">
          {batch.status}
        </span>
        {` · ${batch.videos_count} video(s) × ${batch.clips_per_video} clip(s)`}
        {` · Platforms: ${platforms.join(", ")}`}
        {` · Stagger: ${batch.stagger_gap_minutes} min`}
      </p>

      {batch.error_message && <p className="error">{batch.error_message}</p>}

      <div className="panel">
        <div className="table-scroll">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Video</th>
                <th>Clip</th>
                <th>Title</th>
                <th>Status</th>
                <th>Scheduled upload</th>
              </tr>
            </thead>
            <tbody id="batch-clips-body">
              {clips.length === 0 && (
                <tr>
                  <td colSpan={5}>Generating clips...</td>
                </tr>
              )}
              {clips.map((clip) => {
                const queued = clip.status === "succeeded" && clip.scheduled_upload_at;
                const badgeClass = queued ? "queued" : clip.status;
                const badgeText = queued ? "queued" : clip.status;
                return (
                  <tr key={clip.run_id}>
                    <td>{clip.video_rank}</td>
                    <td>{clip.clip_rank}</td>
                    <td>
                      <Link href={`/runs/${clip.run_id}`}>{clip.metadata_title || clip.run_id}</Link>
                    </td>
                    <td>
                      <span className={`badge badge-${badgeClass}`}>{badgeText}</span>
                    </td>
                    <td>{clip.scheduled_upload_at || "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
