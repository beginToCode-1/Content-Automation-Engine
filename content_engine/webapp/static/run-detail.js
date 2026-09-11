let sinceId = 0;
let lastStatus = INITIAL_STATUS;

const statusEl = document.getElementById("run-status");
const stageEl = document.getElementById("run-stage");
const eventList = document.getElementById("event-list");

async function poll() {
  try {
    const response = await fetch(`/api/runs/${RUN_ID}?since_id=${sinceId}`);
    if (!response.ok) return;
    const data = await response.json();

    statusEl.textContent = data.run.status;
    statusEl.className = "badge badge-" + data.run.status;
    stageEl.textContent = data.run.current_stage || "-";

    for (const event of data.events) {
      const li = document.createElement("li");
      li.textContent = `[${event.stage}] ${event.message}`;
      eventList.appendChild(li);
      sinceId = Math.max(sinceId, event.id);
    }

    if (data.run.status !== lastStatus && (data.run.status === "succeeded" || data.run.status === "failed")) {
      window.location.reload();
      return;
    }
    lastStatus = data.run.status;
  } catch (e) {
    // transient network error - keep polling
  }

  if (lastStatus === "pending" || lastStatus === "running") {
    setTimeout(poll, 2000);
  }
}

if (INITIAL_STATUS === "pending" || INITIAL_STATUS === "running") {
  setTimeout(poll, 2000);
}

const cancelUploadBtn = document.getElementById("cancel-upload-btn");
if (cancelUploadBtn) {
  cancelUploadBtn.addEventListener("click", async () => {
    cancelUploadBtn.disabled = true;
    try {
      const response = await fetch(`/api/runs/${RUN_ID}/cancel-upload`, { method: "POST" });
      if (response.ok) {
        window.location.reload();
      } else {
        cancelUploadBtn.disabled = false;
      }
    } catch (e) {
      cancelUploadBtn.disabled = false;
    }
  });
}
