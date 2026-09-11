"use client";

import { relativeLabel, relativeTitle } from "@/lib/relativeTime";

// Port of the `[data-timestamp]` elements relative-time.js decorates. Since
// every page here is client-rendered (fetches after mount), we can just
// compute the label directly at render time - no hydration mismatch risk,
// and no periodic re-render was done by the original either (it only ran
// once, on DOMContentLoaded).
export default function RelativeTime({ value }: { value: string }) {
  return <span title={relativeTitle(value)}>{relativeLabel(value)}</span>;
}
