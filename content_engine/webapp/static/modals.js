let activeBackdrop = null;
let activePoll = null;

function closeModal() {
  if (activePoll) {
    clearInterval(activePoll);
    activePoll = null;
  }
  if (!activeBackdrop) return;
  activeBackdrop.classList.remove("open");
  const el = activeBackdrop;
  setTimeout(() => el.remove(), 150);
  activeBackdrop = null;
}

function openModal(innerHtml, { wide = false } = {}) {
  closeModal();
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = '<div class="modal-dialog' + (wide ? " modal-wide" : "") + '">' + innerHtml + "</div>";
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeModal();
  });
  document.body.appendChild(backdrop);
  requestAnimationFrame(() => backdrop.classList.add("open"));
  activeBackdrop = backdrop;
  return backdrop.querySelector(".modal-dialog");
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

async function fetchRun(runId) {
  const res = await fetch("/api/runs/" + runId);
  if (!res.ok) throw new Error("Run not found");
  return res.json();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s || "";
  return div.innerHTML;
}

function modalHeader(title) {
  return (
    '<div class="modal-header"><span class="modal-title">' +
    escapeHtml(title) +
    '</span><button type="button" class="modal-close" data-close-modal aria-label="Close">' +
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div>'
  );
}

function wireCloseButtons(dialog) {
  dialog.querySelectorAll("[data-close-modal]").forEach((btn) => btn.addEventListener("click", closeModal));
}

async function openClipPreview(runId) {
  const dialog = openModal(modalHeader("Loading...") + '<div class="modal-body">Loading run...</div>');
  wireCloseButtons(dialog);
  let data;
  try {
    data = await fetchRun(runId);
  } catch (e) {
    dialog.innerHTML = modalHeader("Error") + '<div class="modal-body">Could not load this run.</div>';
    wireCloseButtons(dialog);
    return;
  }
  const run = data.run;
  const hasClip = !!run.clip_path;
  const uploadsHtml = data.uploads.length
    ? data.uploads
        .map(
          (u) =>
            '<div class="copy-field"><div class="field-label">' +
            escapeHtml(u.platform) +
            "</div>" +
            (u.url
              ? '<a href="' + escapeHtml(u.url) + '" target="_blank" class="copy-field-value" style="display:block;">' + escapeHtml(u.url) + "</a>"
              : '<div class="copy-field-value">' + escapeHtml(u.status) + "</div>") +
            "</div>"
        )
        .join("")
    : '<p class="meta-line">No upload attempts yet.</p>';

  dialog.innerHTML =
    modalHeader(run.topic) +
    '<div class="modal-body">' +
    '<div class="modal-split">' +
    "<div>" +
    (hasClip
      ? '<div class="phone-frame"><video controls src="/media/' + run.run_id + '/clip.mp4"></video></div>'
      : '<div class="preview-box"><div class="preview-box-text">No clip rendered for this run.</div></div>') +
    (hasClip
      ? '<a href="/media/' + run.run_id + '/clip.mp4" class="btn-secondary" style="display:block; text-align:center; margin-top:14px;" download>Download Master MP4</a>'
      : "") +
    "</div>" +
    "<div>" +
    '<h2 style="margin-bottom:10px;">' +
    escapeHtml(run.metadata_title || run.topic) +
    "</h2>" +
    '<p class="meta-line" style="margin-bottom:18px;">' +
    escapeHtml(run.metadata_description || "") +
    "</p>" +
    '<h2 style="margin-bottom:10px; font-size:0.9rem;">Uploads</h2>' +
    uploadsHtml +
    "</div>" +
    "</div>" +
    "</div>";
  wireCloseButtons(dialog);
}

function copyFieldHtml(label, value) {
  const safeValue = escapeHtml(value || "");
  return (
    '<div class="copy-field"><div class="field-label">' +
    escapeHtml(label) +
    '</div><div class="copy-field-row"><div class="copy-field-value">' +
    safeValue +
    '</div><button type="button" class="copy-btn" data-copy="' +
    encodeURIComponent(value || "") +
    '" title="Copy">' +
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><rect x="9" y="9" width="12" height="12" rx="2" stroke="currentColor" stroke-width="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10" stroke="currentColor" stroke-width="2"/></svg>' +
    "</button></div></div>"
  );
}

function wireCopyButtons(dialog, allText) {
  dialog.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = decodeURIComponent(btn.getAttribute("data-copy"));
      try {
        await navigator.clipboard.writeText(value);
        btn.classList.add("copied");
        setTimeout(() => btn.classList.remove("copied"), 1200);
      } catch (e) {}
    });
  });
  const copyAllBtn = dialog.querySelector("[data-copy-all]");
  if (copyAllBtn) {
    copyAllBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(allText);
        copyAllBtn.textContent = "Copied!";
        setTimeout(() => (copyAllBtn.textContent = "Copy All for Upload"), 1200);
      } catch (e) {}
    });
  }
}

async function openMetadataInspector(runId) {
  const dialog = openModal(modalHeader("Loading...") + '<div class="modal-body">Loading metadata...</div>');
  wireCloseButtons(dialog);
  let data;
  try {
    data = await fetchRun(runId);
  } catch (e) {
    dialog.innerHTML = modalHeader("Error") + '<div class="modal-body">Could not load this run.</div>';
    wireCloseButtons(dialog);
    return;
  }
  const run = data.run;
  let hashtags = [];
  try {
    hashtags = run.metadata_hashtags ? JSON.parse(run.metadata_hashtags) : [];
  } catch (e) {}
  const hashtagText = hashtags.map((h) => "#" + h).join(" ");

  if (!run.metadata_title) {
    dialog.innerHTML = modalHeader("Metadata") + '<div class="modal-body"><p class="meta-line">No metadata has been generated for this run yet.</p></div>';
    wireCloseButtons(dialog);
    return;
  }

  const allText = [run.metadata_title, run.metadata_description, hashtagText].filter(Boolean).join("\n\n");

  dialog.innerHTML =
    modalHeader("Metadata Inspector") +
    '<div class="modal-body">' +
    copyFieldHtml("Title", run.metadata_title) +
    copyFieldHtml("Description", run.metadata_description) +
    copyFieldHtml("Hashtags", hashtagText) +
    '<button type="button" class="btn-run" data-copy-all style="margin-top:6px;"><span class="btn-run-inner">Copy All for Upload</span></button>' +
    "</div>";
  wireCloseButtons(dialog);
  wireCopyButtons(dialog, allText);
}

async function openDiagnostic(runId, onResolved) {
  const dialog = openModal(modalHeader("Loading...") + '<div class="modal-body">Loading diagnostics...</div>');
  wireCloseButtons(dialog);
  let data;
  try {
    data = await fetchRun(runId);
  } catch (e) {
    dialog.innerHTML = modalHeader("Error") + '<div class="modal-body">Could not load this run.</div>';
    wireCloseButtons(dialog);
    return;
  }
  renderDiagnostic(dialog, data.run, onResolved);
}

function renderDiagnostic(dialog, run, onResolved) {
  const statusBadge = '<span class="badge badge-' + run.status + '">' + run.status + "</span>";
  dialog.innerHTML =
    modalHeader("Diagnostics - " + run.topic) +
    '<div class="modal-body">' +
    '<div class="diagnostic-status-row">' +
    statusBadge +
    '<span class="meta-line">Stage: ' +
    escapeHtml(run.current_stage || "-") +
    "</span>" +
    "</div>" +
    (run.error_message
      ? '<div class="diagnostic-error">' + escapeHtml(run.error_message) + "</div>"
      : '<p class="meta-line" style="margin-bottom:18px;">No error recorded.</p>') +
    (run.status === "failed"
      ? '<button type="button" class="btn-run" id="diagnostic-retry-btn"><span class="btn-run-inner">Retry Pipeline Now</span></button>' +
        '<div class="status-text" id="diagnostic-retry-status" style="margin-left:0; margin-top:8px;"></div>'
      : "") +
    "</div>";
  wireCloseButtons(dialog);

  const retryBtn = dialog.querySelector("#diagnostic-retry-btn");
  if (retryBtn) {
    retryBtn.addEventListener("click", async () => {
      retryBtn.disabled = true;
      const statusEl = dialog.querySelector("#diagnostic-retry-status");
      statusEl.textContent = "Retrying...";
      try {
        const res = await fetch("/api/runs/" + run.run_id + "/retry", { method: "POST" });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          statusEl.textContent = "Retry failed: " + (err.detail || res.statusText);
          retryBtn.disabled = false;
          return;
        }
        const body = await res.json();
        const pollId = body.run_id;
        statusEl.textContent = "Retrying - watching for a result...";
        activePoll = setInterval(async () => {
          try {
            const check = await fetchRun(pollId);
            if (check.run.status === "succeeded" || check.run.status === "failed") {
              clearInterval(activePoll);
              activePoll = null;
              renderDiagnostic(dialog, check.run, onResolved);
              if (onResolved) onResolved(check.run);
            }
          } catch (e) {}
        }, 2000);
      } catch (e) {
        statusEl.textContent = "Retry failed: " + e.message;
        retryBtn.disabled = false;
      }
    });
  }
}
