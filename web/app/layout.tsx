import type { Metadata } from "next";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Content Engine",
  description: "Upload once, publish everywhere",
  icons: {
    icon:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='6' fill='%231a73e8'/%3E%3Cpolygon points='9,7 18,12 9,17' fill='white'/%3E%3C/svg%3E",
  },
};

// Applies a persisted theme before first paint (mirrors the inline <script>
// in base.html's <head>) so there's no light/dark flash on load. Dark is the
// implicit default (see ThemeToggle.tsx), so this only ever needs to act
// when "light" was explicitly saved.
const themeInitScript = `
(function () {
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Loaded as a plain <link>, not next/font, to match base.html's head
            exactly (same Google Fonts request, same families/weights). */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700&family=Roboto+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="main-area">
            <main className="container">{children}</main>
            <footer className="site-footer">
              <span>Content Engine</span>
              <Link href="/privacy">Privacy Policy</Link>
              <Link href="/terms">Terms of Service</Link>
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}
