const searchInput = document.getElementById("library-search");
const statusTabs = document.getElementById("status-filter-tabs");
const platformFilter = document.getElementById("platform-filter");
const rows = Array.from(document.querySelectorAll("#library-rows tr[data-status]"));
const countLabel = document.getElementById("library-count-label");

let activeStatus = "all";

function applyFilters() {
  const query = searchInput.value.trim().toLowerCase();
  const platform = platformFilter.value;
  let visible = 0;

  rows.forEach((row) => {
    const matchesStatus = activeStatus === "all" || row.dataset.status === activeStatus;
    const matchesPlatform = !platform || row.dataset.platforms.split(",").includes(platform);
    const matchesSearch = !query || row.dataset.search.includes(query);
    const show = matchesStatus && matchesPlatform && matchesSearch;
    row.hidden = !show;
    if (show) visible++;
  });

  countLabel.textContent = "Showing " + visible + " of " + rows.length + " runs";
}

searchInput.addEventListener("input", applyFilters);
platformFilter.addEventListener("change", applyFilters);

statusTabs.querySelectorAll("button").forEach((btn) => {
  btn.addEventListener("click", () => {
    statusTabs.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeStatus = btn.dataset.status;
    applyFilters();
  });
});

document.querySelectorAll(".preview-trigger").forEach((btn) => {
  btn.addEventListener("click", () => openClipPreview(btn.dataset.runId));
});

document.querySelectorAll(".metadata-trigger").forEach((btn) => {
  btn.addEventListener("click", () => openMetadataInspector(btn.dataset.runId));
});

document.querySelectorAll(".diagnostic-trigger").forEach((badge) => {
  badge.addEventListener("click", () => {
    openDiagnostic(badge.dataset.runId, (updatedRun) => {
      const row = document.querySelector('tr[data-status] td .diagnostic-trigger[data-run-id="' + updatedRun.run_id + '"]');
      if (!row) return;
      const cell = row.closest("td");
      cell.innerHTML =
        updatedRun.status === "failed"
          ? '<span class="badge badge-failed diagnostic-trigger" data-run-id="' +
            updatedRun.run_id +
            '" style="cursor:pointer;" title="Click for diagnostics">failed</span>'
          : '<span class="badge badge-' + updatedRun.status + '">' + updatedRun.status + "</span>";
      if (updatedRun.status === "failed") {
        cell.querySelector(".diagnostic-trigger").addEventListener("click", () => openDiagnostic(updatedRun.run_id));
      }
    });
  });
});

document.querySelectorAll(".retry-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const runId = btn.dataset.runId;
    btn.disabled = true;
    btn.textContent = "Retrying...";
    try {
      const response = await fetch("/api/runs/" + runId + "/retry", { method: "POST" });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        alert("Retry failed: " + (err.detail || response.statusText));
        btn.disabled = false;
        btn.textContent = "Retry";
        return;
      }
      const data = await response.json();
      window.location.href = "/runs/" + data.run_id;
    } catch (e) {
      alert("Retry failed: " + e.message);
      btn.disabled = false;
      btn.textContent = "Retry";
    }
  });
});
