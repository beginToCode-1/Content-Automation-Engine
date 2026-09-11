(function () {
  function relativeLabel(isoString) {
    const then = new Date(isoString.endsWith("Z") ? isoString : isoString + "Z");
    if (isNaN(then.getTime())) return isoString;
    const diffMs = Date.now() - then.getTime();
    const diffSec = Math.round(diffMs / 1000);

    if (diffSec < 45) return "just now";
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return diffMin + "m ago";
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return diffHr + "h ago";
    const diffDay = Math.round(diffHr / 24);
    if (diffDay < 7) return diffDay + "d ago";

    const sameYear = then.getFullYear() === new Date().getFullYear();
    return then.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: sameYear ? undefined : "numeric",
    });
  }

  function applyRelativeTimes(root) {
    (root || document).querySelectorAll("[data-timestamp]").forEach((el) => {
      const raw = el.getAttribute("data-timestamp");
      if (!raw) return;
      el.textContent = relativeLabel(raw);
      el.title = raw.replace("T", " ").replace("Z", " UTC");
    });
  }

  window.applyRelativeTimes = applyRelativeTimes;
  document.addEventListener("DOMContentLoaded", () => applyRelativeTimes());
})();
