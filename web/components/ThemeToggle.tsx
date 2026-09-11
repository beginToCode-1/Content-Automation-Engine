"use client";

// Port of the theme-toggle portion of static/shell.js.
export default function ThemeToggle() {
  function handleClick() {
    const root = document.documentElement;
    // Dark is the unconditional default in the CSS (no @media
    // prefers-color-scheme branch exists) - so the fallback here must match
    // that, not the OS preference, or the very first toggle click computes
    // the wrong "next" state.
    const current = root.getAttribute("data-theme") || "dark";
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      // ignore - theme just won't persist
    }
  }

  return (
    <button
      type="button"
      className="theme-toggle-btn"
      id="theme-toggle-btn"
      title="Toggle light/dark theme"
      aria-label="Toggle theme"
      onClick={handleClick}
    >
      <svg className="icon-sun" width="16" height="16" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
        <path
          d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      <svg className="icon-moon" width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path
          d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
