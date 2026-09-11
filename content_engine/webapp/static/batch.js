const form = document.getElementById("new-batch-form");

function formatOffset(totalMinutes) {
  if (totalMinutes < 60) return "+" + totalMinutes + "m";
  const hours = totalMinutes / 60;
  return "+" + (Number.isInteger(hours) ? hours : hours.toFixed(1)) + "h";
}

function updateBatchPreview() {
  const videosInput = document.getElementById("batch-videos-count");
  const clipsInput = document.getElementById("batch-clips-per-video");
  const staggerInput = document.getElementById("batch-stagger");
  const yieldEl = document.getElementById("batch-yield-indicator");
  const timelineEl = document.getElementById("batch-stagger-timeline");
  if (!videosInput || !clipsInput || !staggerInput || !yieldEl || !timelineEl) return;

  const videos = Math.max(1, parseInt(videosInput.value, 10) || 1);
  const clipsPerVideo = Math.max(1, parseInt(clipsInput.value, 10) || 1);
  const stagger = Math.max(1, parseInt(staggerInput.value, 10) || 1);
  const totalClips = videos * clipsPerVideo;

  yieldEl.textContent = "Yield: " + totalClips + " Scheduled Short" + (totalClips === 1 ? "" : "s");

  // Mirrors the real scheduling formula in batch_executor.py exactly:
  // clip i (1-based, across the whole batch) uploads at now + i * stagger_gap_minutes.
  const maxBadges = 8;
  const shown = Math.min(totalClips, maxBadges);
  let html = "";
  for (let i = 1; i <= shown; i++) {
    html += '<span class="stagger-badge">' + formatOffset(i * stagger) + "</span>";
  }
  if (totalClips > maxBadges) {
    html += '<span class="stagger-badge">+' + (totalClips - maxBadges) + " more</span>";
  }
  timelineEl.innerHTML = html;
}

["batch-videos-count", "batch-clips-per-video", "batch-stagger"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("input", updateBatchPreview);
});
updateBatchPreview();

if (form) {
  const statusEl = document.getElementById("new-batch-status");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const platforms = formData.getAll("platforms");
    if (!platforms.length) {
      statusEl.textContent = "Select at least one platform.";
      return;
    }

    statusEl.textContent = "Starting.";

    try {
      const response = await fetch("/api/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: formData.get("topic"),
          platforms: platforms,
          videos_count: parseInt(formData.get("videos_count"), 10),
          clips_per_video: parseInt(formData.get("clips_per_video"), 10),
          stagger_gap_minutes: parseInt(formData.get("stagger_gap_minutes"), 10),
          privacy: formData.get("privacy"),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        statusEl.textContent = "Error: " + (err.detail || response.statusText);
        return;
      }

      const data = await response.json();
      window.location.href = "/batch/" + data.batch_id;
    } catch (e) {
      statusEl.textContent = "Error: " + e.message;
    }
  });
}

if (typeof BATCH_ID !== "undefined") {
  const tbody = document.getElementById("batch-clips-body");
  const statusEl = document.getElementById("batch-status");

  async function poll() {
    try {
      const res = await fetch("/api/batches/" + BATCH_ID);
      if (res.ok) {
        const data = await res.json();
        statusEl.textContent = data.batch.status;
        statusEl.className = "badge badge-" + (data.batch.status === "running" ? "running" : data.batch.status);

        if (data.clips.length) {
          tbody.innerHTML = data.clips
            .map((clip) => {
              const queued = clip.status === "succeeded" && clip.scheduled_upload_at;
              const badgeClass = queued ? "queued" : clip.status;
              const badgeText = queued ? "queued" : clip.status;
              return (
                "<tr><td>" +
                clip.video_rank +
                "</td><td>" +
                clip.clip_rank +
                '</td><td><a href="/runs/' +
                clip.run_id +
                '">' +
                (clip.metadata_title || clip.run_id) +
                '</a></td><td><span class="badge badge-' +
                badgeClass +
                '">' +
                badgeText +
                "</span></td><td>" +
                (clip.scheduled_upload_at || "-") +
                "</td></tr>"
              );
            })
            .join("");
        }

        if (data.batch.status !== "running") {
          return;
        }
      }
    } catch (e) {
      // transient network error - keep polling
    }
    setTimeout(poll, 3000);
  }
  poll();
}
