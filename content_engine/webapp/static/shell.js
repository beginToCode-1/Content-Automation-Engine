(function () {
  const root = document.documentElement;
  const themeBtn = document.getElementById("theme-toggle-btn");

  function currentTheme() {
    // Dark is the unconditional default in the CSS (no @media prefers-color-scheme
    // branch exists) - so the fallback here must match that, not the OS preference,
    // or the very first toggle click computes the wrong "next" state.
    return root.getAttribute("data-theme") || "dark";
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (e) {}
    });
  }

  const sidebar = document.getElementById("sidebar");
  const collapseBtn = document.getElementById("sidebar-collapse-btn");

  if (sidebar && collapseBtn) {
    try {
      if (localStorage.getItem("sidebarCollapsed") === "true") {
        sidebar.classList.add("collapsed");
      }
    } catch (e) {}

    collapseBtn.addEventListener("click", () => {
      const collapsed = sidebar.classList.toggle("collapsed");
      try {
        localStorage.setItem("sidebarCollapsed", collapsed ? "true" : "false");
      } catch (e) {}
    });
  }
})();
