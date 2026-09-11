let draftId = null;

const draftForm = document.getElementById("draft-form");
const draftStatus = document.getElementById("draft-status");
const publishPanel = document.getElementById("publish-panel");
const publishForm = document.getElementById("publish-form");
const publishStatus = document.getElementById("publish-status");

const fileInput = document.getElementById("upload-file");
const dropzone = document.getElementById("dropzone");
const fileCard = document.getElementById("file-card");
const fileCardName = document.getElementById("file-card-name");
const fileCardMeta = document.getElementById("file-card-meta");
const fileCardRemove = document.getElementById("file-card-remove");

function formatBytes(bytes) {
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

function formatDuration(seconds) {
  if (!isFinite(seconds)) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m + ":" + String(s).padStart(2, "0");
}

function showFileCard(file) {
  dropzone.hidden = true;
  fileCard.hidden = false;
  fileCardName.textContent = file.name;
  fileCardMeta.textContent = formatBytes(file.size);

  // Real duration/resolution, read directly from the actual file - not fabricated.
  const probe = document.createElement("video");
  probe.preload = "metadata";
  probe.src = URL.createObjectURL(file);
  probe.onloadedmetadata = () => {
    const duration = formatDuration(probe.duration);
    const parts = [formatBytes(file.size)];
    if (duration) parts.push(duration);
    if (probe.videoWidth && probe.videoHeight) parts.push(probe.videoWidth + "x" + probe.videoHeight);
    fileCardMeta.textContent = parts.join(" · ");
    URL.revokeObjectURL(probe.src);
  };
}

function clearFile() {
  fileInput.value = "";
  dropzone.hidden = false;
  fileCard.hidden = true;
}

function assignFiles(fileList) {
  if (!fileList || !fileList.length) return;
  const file = fileList[0];
  if (!file.name.toLowerCase().endsWith(".mp4")) {
    draftStatus.textContent = "Only .mp4 files are supported.";
    return;
  }
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
  showFileCard(file);
}

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  assignFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => assignFiles(fileInput.files));
fileCardRemove.addEventListener("click", clearFile);

draftForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(draftForm);
  draftStatus.textContent = "Generating draft metadata.";

  try {
    const response = await fetch("/api/self-upload/draft", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      draftStatus.textContent = "Error: " + (err.detail || response.statusText);
      return;
    }

    const data = await response.json();
    draftId = data.draft_id;
    document.getElementById("publish-title").value = data.metadata.title;
    document.getElementById("publish-description").value = data.metadata.description;
    document.getElementById("publish-hashtags").value = data.metadata.hashtags.join(", ");
    draftStatus.textContent = "Draft ready. Review below before publishing.";
    publishPanel.hidden = false;
    publishPanel.scrollIntoView({ behavior: "smooth" });
    requestAnimationFrame(() => {
      requestAnimationFrame(() => publishPanel.classList.add("materialized"));
    });
  } catch (e) {
    draftStatus.textContent = "Error: " + e.message;
  }
});

publishForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!draftId) {
    publishStatus.textContent = "Generate a draft first.";
    return;
  }

  const formData = new FormData(publishForm);
  const platforms = formData.getAll("platforms");
  if (!platforms.length) {
    publishStatus.textContent = "Select at least one platform.";
    return;
  }

  const hashtags = (formData.get("hashtags") || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

  publishStatus.textContent = "Publishing.";

  try {
    const response = await fetch("/api/self-upload/" + draftId + "/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: formData.get("title"),
        description: formData.get("description"),
        hashtags: hashtags,
        platforms: platforms,
        privacy: formData.get("privacy"),
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      publishStatus.textContent = "Error: " + (err.detail || response.statusText);
      return;
    }

    const data = await response.json();
    window.location.href = "/runs/" + data.run_id;
  } catch (e) {
    publishStatus.textContent = "Error: " + e.message;
  }
});
