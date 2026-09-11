"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import PageHeader from "@/components/PageHeader";
import { apiUrl } from "@/lib/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  const units = ["KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = -1;
  do {
    value /= 1024;
    unitIndex++;
  } while (value >= 1024 && unitIndex < units.length - 1);
  return value.toFixed(value < 10 ? 1 : 0) + " " + units[unitIndex];
}

function formatDuration(seconds: number): string | null {
  if (!isFinite(seconds)) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m + ":" + String(s).padStart(2, "0");
}

export default function SelfUploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileMeta, setFileMeta] = useState("");
  const [dragover, setDragover] = useState(false);
  const [hint, setHint] = useState("");
  const [draftStatus, setDraftStatus] = useState("");
  const [draftSubmitting, setDraftSubmitting] = useState(false);
  const [draftId, setDraftId] = useState<string | null>(null);

  const [publishVisible, setPublishVisible] = useState(false);
  const [materialized, setMaterialized] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["youtube"]);
  const [privacy, setPrivacy] = useState("private");
  const [publishStatus, setPublishStatus] = useState("");
  const [publishSubmitting, setPublishSubmitting] = useState(false);

  function assignFile(f: File) {
    if (!f.name.toLowerCase().endsWith(".mp4")) {
      setDraftStatus("Only .mp4 files are supported.");
      return;
    }
    setFile(f);
    setFileMeta(formatBytes(f.size));

    const probe = document.createElement("video");
    probe.preload = "metadata";
    probe.src = URL.createObjectURL(f);
    probe.onloadedmetadata = () => {
      const duration = formatDuration(probe.duration);
      const parts = [formatBytes(f.size)];
      if (duration) parts.push(duration);
      if (probe.videoWidth && probe.videoHeight) parts.push(probe.videoWidth + "x" + probe.videoHeight);
      setFileMeta(parts.join(" · "));
      URL.revokeObjectURL(probe.src);
    };
  }

  function clearFile() {
    setFile(null);
    setFileMeta("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function togglePlatform(value: string, checked: boolean) {
    setPlatforms((prev) => (checked ? [...prev, value] : prev.filter((p) => p !== value)));
  }

  async function handleDraftSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setDraftStatus("Choose a video file.");
      return;
    }
    if (!hint.trim()) {
      setDraftStatus("A topic or context hint is required.");
      return;
    }
    setDraftStatus("Generating draft metadata.");
    setDraftSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("hint", hint);
      const response = await fetch(apiUrl("/api/self-upload/draft"), { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setDraftStatus("Error: " + (err.detail || response.statusText));
        return;
      }
      const data = await response.json();
      setDraftId(data.draft_id);
      setTitle(data.metadata.title);
      setDescription(data.metadata.description);
      setHashtags(data.metadata.hashtags.join(", "));
      setDraftStatus("Draft ready. Review below before publishing.");
      setPublishVisible(true);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setMaterialized(true));
      });
    } catch (e) {
      setDraftStatus("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setDraftSubmitting(false);
    }
  }

  async function handlePublishSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draftId) {
      setPublishStatus("Generate a draft first.");
      return;
    }
    if (!platforms.length) {
      setPublishStatus("Select at least one platform.");
      return;
    }
    const hashtagList = hashtags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    setPublishStatus("Publishing.");
    setPublishSubmitting(true);
    try {
      const response = await fetch(apiUrl(`/api/self-upload/${draftId}/publish`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description, hashtags: hashtagList, platforms, privacy }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setPublishStatus("Error: " + (err.detail || response.statusText));
        return;
      }
      const data = await response.json();
      router.push(`/runs/${data.run_id}`);
    } catch (e) {
      setPublishStatus("Error: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setPublishSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        breadcrumb="Upload"
        title="Upload & Ingestion"
        subtitle="Import your own video, generate a metadata draft, and publish it to your platforms."
      />

      <div className="info-banner">
        <span className="info-banner-icon">i</span>
        <span className="info-banner-text">
          Your video is not modified in any way. Generating a draft only creates suggested metadata - nothing
          publishes until you review and confirm on the next step.
        </span>
      </div>

      <div className="panel form-panel" id="draft-panel">
        <div className="panel-header">
          <h2>Upload Your Own Video</h2>
        </div>

        <form id="draft-form" onSubmit={handleDraftSubmit}>
          <div className="field">
            <label className="field-label">Video file</label>
            <input
              type="file"
              id="upload-file"
              name="file"
              accept="video/mp4"
              required
              hidden
              ref={fileInputRef}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) assignFile(f);
              }}
            />

            {!file && (
              <div
                className={`dropzone${dragover ? " dragover" : ""}`}
                tabIndex={0}
                role="button"
                aria-label="Choose a video file"
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragover(true);
                }}
                onDragLeave={() => setDragover(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragover(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) assignFile(f);
                }}
              >
                <div className="dropzone-icon">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
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
                </div>
                <div className="dropzone-text">Click to upload or drag and drop</div>
                <div className="dropzone-tags">
                  <span className="format-tag">MP4</span>
                </div>
              </div>
            )}

            {file && (
              <div className="file-card" id="file-card">
                <div className="file-card-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="2" />
                    <path d="M10 9l5 3-5 3V9z" fill="currentColor" />
                  </svg>
                </div>
                <div className="file-card-info">
                  <div className="file-card-name">{file.name}</div>
                  <div className="file-card-meta">{fileMeta}</div>
                </div>
                <button
                  type="button"
                  className="btn-icon"
                  title="Remove file"
                  aria-label="Remove file"
                  onClick={clearFile}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            )}

            <div className="field-hint">Uploaded as-is - no cropping, captions, or re-encoding.</div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="upload-hint">
              Topic or context hint
            </label>
            <input
              type="text"
              id="upload-hint"
              name="hint"
              placeholder="e.g. morning workout routine"
              required
              value={hint}
              onChange={(e) => setHint(e.target.value)}
            />
            <div className="field-hint">A short description used to generate the title, description, and hashtags.</div>
          </div>

          <button type="submit" className="btn-run" disabled={draftSubmitting}>
            <span className="btn-run-inner">Generate Draft</span>
          </button>
          <div id="draft-status" className="status-text">
            {draftStatus}
          </div>
        </form>
      </div>

      {publishVisible && (
        <div
          className={`panel form-panel${materialized ? " materialized" : ""}`}
          id="publish-panel"
          style={{ marginTop: 20 }}
        >
          <div className="panel-header">
            <h2>Review and Publish</h2>
          </div>

          <form id="publish-form" onSubmit={handlePublishSubmit}>
            <div className="field">
              <label className="field-label" htmlFor="publish-title">
                Title
              </label>
              <input
                type="text"
                id="publish-title"
                name="title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="publish-description">
                Description
              </label>
              <input
                type="text"
                id="publish-description"
                name="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="publish-hashtags">
                Hashtags (comma-separated)
              </label>
              <input
                type="text"
                id="publish-hashtags"
                name="hashtags"
                value={hashtags}
                onChange={(e) => setHashtags(e.target.value)}
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
              <label className="field-label">Upload privacy</label>
              <div className="segmented">
                <input
                  type="radio"
                  name="privacy"
                  value="private"
                  id="publish-privacy-private"
                  checked={privacy === "private"}
                  onChange={() => setPrivacy("private")}
                />
                <label htmlFor="publish-privacy-private">Private</label>
                <input
                  type="radio"
                  name="privacy"
                  value="public"
                  id="publish-privacy-public"
                  checked={privacy === "public"}
                  onChange={() => setPrivacy("public")}
                />
                <label htmlFor="publish-privacy-public">Public</label>
              </div>
            </div>

            <button type="submit" className="btn-run" disabled={publishSubmitting}>
              <span className="btn-run-inner">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <polygon points="6,4 20,12 6,20" fill="currentColor" />
                </svg>
                Publish
              </span>
            </button>
            <div id="publish-status" className="status-text">
              {publishStatus}
            </div>
          </form>
        </div>
      )}
    </>
  );
}
