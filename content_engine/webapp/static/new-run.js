const STAGE_STEPS = [
  { key: "search", label: "Sourcing and Selecting Video" },
  { key: "download", label: "Downloading Source Media" },
  { key: "transcript", label: "Fetching Transcript" },
  { key: "segment", label: "Selecting Best Segment" },
  { key: "render", label: "Rendering 9:16 and Captions" },
  { key: "metadata", label: "Generating Metadata" },
  { key: "upload", label: "Publishing to Platforms" },
];

const CHECK_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><polyline points="4,12 9,17 20,6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CROSS_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>';
const CHEVRON_ICON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" style="vertical-align:-1px"><polyline points="9,5 16,12 9,19" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function stageIndexForKey(stageKey) {
  if (!stageKey) return -1;
  const normalized = stageKey.startsWith("upload") ? "upload" : stageKey;
  return STAGE_STEPS.findIndex((s) => s.key === normalized);
}

function renderStageList(highestIndex, status) {
  const list = document.getElementById("stage-list");
  list.innerHTML = "";
  STAGE_STEPS.forEach((step, i) => {
    let stateClass = "pending";
    let iconHtml = '<span class="stage-dot"></span>';
    if (i < highestIndex) {
      stateClass = "done";
      iconHtml = '<span class="stage-check">' + CHECK_ICON + "</span>";
    } else if (i === highestIndex) {
      if (status === "failed") {
        stateClass = "failed";
        iconHtml = '<span style="color:var(--danger)">' + CROSS_ICON + "</span>";
      } else if (status === "succeeded") {
        stateClass = "done";
        iconHtml = '<span class="stage-check">' + CHECK_ICON + "</span>";
      } else {
        stateClass = "active";
      }
    }
    const row = document.createElement("div");
    row.className = "stage-row " + stateClass;
    row.innerHTML =
      '<div class="stage-row-left"><span class="stage-num">0' +
      (i + 1) +
      '</span><span class="stage-title">' +
      step.label +
      "</span></div>" +
      iconHtml;
    list.appendChild(row);
  });
}

function startPolling(runId, topic) {
  let sinceId = 0;
  document.getElementById("monitor-title").textContent = "Tracking: " + topic;
  document.getElementById("live-dot").classList.remove("idle");
  document.getElementById("preview-text").textContent = "Pipeline starting.";
  renderStageList(0, "running");

  async function poll() {
    try {
      const res = await fetch("/api/runs/" + runId + "?since_id=" + sinceId);
      if (res.ok) {
        const data = await res.json();
        for (const event of data.events) {
          sinceId = Math.max(sinceId, event.id);
        }

        const idx = stageIndexForKey(data.run.current_stage);
        const effectiveIdx = idx === -1 ? 0 : idx;
        renderStageList(effectiveIdx, data.run.status);

        if (data.run.status === "succeeded") {
          document.getElementById("preview-text").innerHTML =
            'Run complete. <a href="/runs/' + runId + '">View full run ' + CHEVRON_ICON + "</a>";
          document.getElementById("live-dot").classList.add("idle");
          return;
        }
        if (data.run.status === "failed") {
          document.getElementById("preview-text").innerHTML =
            "Run failed: " +
            (data.run.error_message || "see run detail") +
            '. <a href="/runs/' +
            runId +
            '">View full run ' +
            CHEVRON_ICON +
            "</a>";
          document.getElementById("live-dot").classList.add("idle");
          return;
        }
        document.getElementById("preview-text").textContent = "Rendering vertical short-form preview.";
      }
    } catch (e) {
      // transient network error - keep polling
    }
    setTimeout(poll, 2000);
  }
  poll();
}

document.querySelectorAll(".toggle-chip input[type=checkbox]").forEach((cb) => {
  cb.addEventListener("change", () => {
    cb.closest(".toggle-chip").classList.toggle("checked", cb.checked);
  });
});

const form = document.getElementById("new-run-form");
const statusEl = document.getElementById("new-run-status");

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
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: formData.get("topic"),
        mode: formData.get("mode"),
        platforms: platforms,
        privacy: formData.get("privacy"),
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      statusEl.textContent = "Error: " + (err.detail || response.statusText);
      return;
    }

    const data = await response.json();
    statusEl.textContent = "";
    startPolling(data.run_id, formData.get("topic"));
  } catch (e) {
    statusEl.textContent = "Error: " + e.message;
  }
});

renderStageList(-1, "pending");
