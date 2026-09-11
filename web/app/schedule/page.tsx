"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import YouTubeAccountPicker from "@/components/YouTubeAccountPicker";
import { apiFetch, platformsFromStr, type ScheduleEntry } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function SchedulePage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [schedules, setSchedules] = useState<ScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [topic, setTopic] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["youtube"]);
  const [youtubeAccountId, setYoutubeAccountId] = useState<string | null>(null);
  const [recurrence, setRecurrence] = useState<"once" | "daily">("once");
  const [scheduledTime, setScheduledTime] = useState("");
  const [dailyTime, setDailyTime] = useState("");
  const [statusText, setStatusText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  // Used to refresh the table from event handlers (after adding/cancelling a
  // schedule) - safe to setLoading(true) synchronously here since it's never
  // called directly from an effect body.
  function reloadSchedules() {
    setLoading(true);
    apiFetch<{ schedules: ScheduleEntry[] }>("/api/schedule")
      .then((data) => setSchedules(data.schedules))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    let cancelled = false;
    apiFetch<{ schedules: ScheduleEntry[] }>("/api/schedule")
      .then((data) => {
        if (!cancelled) setSchedules(data.schedules);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function togglePlatform(value: string, checked: boolean) {
    setPlatforms((prev) => (checked ? [...prev, value] : prev.filter((p) => p !== value)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatusText("Saving...");
    setSubmitting(true);
    try {
      await apiFetch("/api/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          recurrence,
          platforms,
          scheduled_time: recurrence === "once" ? scheduledTime : null,
          daily_time: recurrence === "daily" ? dailyTime : null,
          youtube_account_id: platforms.includes("youtube") ? youtubeAccountId : undefined,
        }),
      });
      setStatusText("");
      setTopic("");
      setScheduledTime("");
      setDailyTime("");
      reloadSchedules();
    } catch (e) {
      setStatusText("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel(id: number) {
    setCancellingId(id);
    try {
      await apiFetch(`/api/schedule/${id}/cancel`, { method: "POST" });
      reloadSchedules();
    } catch {
      // matches the previous behavior: a failed cancel just leaves the row as-is
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <>
      <PageHeader
        breadcrumb="Schedule"
        title="Publication Schedule"
        subtitle="Automated recurring topics, always uploaded private for manual review."
      />

      <p className="note" style={{ maxWidth: 640, marginBottom: 20 }}>
        Scheduled runs always upload as <strong>private</strong>, regardless of any other setting. Review and
        publish manually once you are satisfied with the result. There is no way to configure a public scheduled
        upload.
      </p>

      {!isAdmin && (
        <p className="note" style={{ maxWidth: 640, marginBottom: 20 }}>
          Admin access required to add or cancel scheduled topics. You can still review the schedule below.
        </p>
      )}

      <div className="panel form-panel">
        <div className="panel-header">
          <h2>Add a Scheduled Topic</h2>
        </div>

        <form id="new-schedule-form" onSubmit={handleSubmit}>
          <div className="field">
            <label className="field-label" htmlFor="schedule-topic">
              Topic
            </label>
            <input
              type="text"
              id="schedule-topic"
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
            <YouTubeAccountPicker platforms={platforms} value={youtubeAccountId} onChange={setYoutubeAccountId} />
          </div>

          <div className="field">
            <label className="field-label">When</label>
            <div className="segmented" style={{ marginBottom: 10 }}>
              <input
                type="radio"
                name="recurrence"
                value="once"
                id="rec-once"
                checked={recurrence === "once"}
                onChange={() => setRecurrence("once")}
              />
              <label htmlFor="rec-once">Once</label>
              <input
                type="radio"
                name="recurrence"
                value="daily"
                id="rec-daily"
                checked={recurrence === "daily"}
                onChange={() => setRecurrence("daily")}
              />
              <label htmlFor="rec-daily">Daily</label>
            </div>
            <input
              type="datetime-local"
              name="scheduled_time"
              style={{ marginBottom: 8 }}
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
            />
            <input type="time" name="daily_time" value={dailyTime} onChange={(e) => setDailyTime(e.target.value)} />
          </div>

          <button
            type="submit"
            className="btn-run"
            disabled={submitting || !isAdmin}
            title={isAdmin ? undefined : "Admin access required"}
          >
            <span className="btn-run-inner">Add Schedule</span>
          </button>
          <div id="new-schedule-status" className="status-text">
            {statusText}
          </div>
        </form>
      </div>

      <h1 className="section-title">Active Schedules</h1>
      <div className="panel">
        <div className="table-scroll">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Recurrence</th>
                <th>When</th>
                <th>Platforms</th>
                <th>Status</th>
                <th>Last run</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {!loading && schedules.length === 0 && (
                <tr>
                  <td colSpan={7}>No scheduled topics yet.</td>
                </tr>
              )}
              {schedules.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.topic}</td>
                  <td>{entry.recurrence}</td>
                  <td>{entry.scheduled_time || entry.daily_time}</td>
                  <td>{platformsFromStr(entry.target_platforms).join(", ")}</td>
                  <td>{entry.status}</td>
                  <td>{entry.last_run_id ? <Link href={`/runs/${entry.last_run_id}`}>{entry.last_run_id}</Link> : "-"}</td>
                  <td>
                    {entry.status === "active" && isAdmin && (
                      <button
                        type="button"
                        className="btn-secondary cancel-schedule"
                        disabled={cancellingId === entry.id}
                        onClick={() => handleCancel(entry.id)}
                      >
                        Cancel
                      </button>
                    )}
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
