const form = document.getElementById("new-schedule-form");
const statusEl = document.getElementById("new-schedule-status");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const platforms = formData.getAll("platforms");
  const recurrence = formData.get("recurrence");

  statusEl.textContent = "Saving...";

  try {
    const response = await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: formData.get("topic"),
        recurrence: recurrence,
        platforms: platforms,
        scheduled_time: recurrence === "once" ? formData.get("scheduled_time") : null,
        daily_time: recurrence === "daily" ? formData.get("daily_time") : null,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      statusEl.textContent = "Error: " + (err.detail || response.statusText);
      return;
    }

    window.location.reload();
  } catch (e) {
    statusEl.textContent = "Error: " + e.message;
  }
});

document.querySelectorAll(".cancel-schedule").forEach((button) => {
  button.addEventListener("click", async () => {
    const id = button.dataset.id;
    await fetch(`/api/schedule/${id}/cancel`, { method: "POST" });
    window.location.reload();
  });
});
