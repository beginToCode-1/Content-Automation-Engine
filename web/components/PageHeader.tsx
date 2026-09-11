import Link from "next/link";
import type { ReactNode } from "react";
import ThemeToggle from "./ThemeToggle";

interface PageHeaderProps {
  breadcrumb: string;
  title: string;
  subtitle?: string;
  /** Defaults to the "New Production Run" link -> /studio, exactly like base.html's
   * page_header_action block default. Pass `null` to render no action (privacy/terms). */
  action?: ReactNode | null;
}

// Matches base.html's default page_header_action block exactly - it links to
// "/" (Upload & Drafts), not "/studio", unless a page overrides it.
const defaultAction = (
  <Link href="/" className="btn-header-action">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <polygon points="6,4 20,12 6,20" fill="currentColor" />
    </svg>
    New Production Run
  </Link>
);

export default function PageHeader({ breadcrumb, title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div className="page-header-left">
        <div className="breadcrumb">
          <Link href="/" className="crumb-root">
            Content Engine
          </Link>
          <span className="crumb-sep">/</span>
          <span className="crumb-current">{breadcrumb}</span>
        </div>
        <h1 className="page-title">{title}</h1>
        <p className="page-subtitle">{subtitle}</p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <ThemeToggle />
        {action === undefined ? defaultAction : action}
      </div>
    </div>
  );
}
