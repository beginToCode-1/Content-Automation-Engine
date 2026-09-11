// Central place for the backend origin. The frontend (Vercel) and backend
// (Railway/Render) are separate deployments, so every request needs an
// absolute URL - never a relative "/api/..." path like the old server-
// rendered app used (that worked only because the JS and the API shared
// an origin).
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export function mediaUrl(runId: string): string {
  return apiUrl(`/media/${runId}/clip.mp4`);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // ignore - fall through to statusText
  }
  return res.statusText;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), init);
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }
  return (await res.json()) as T;
}

// ---------- Shared domain types (mirroring the JSON API contract) ----------

export interface Channel {
  key: string;
  label: string;
  short: string;
  icon_class: string;
  connected: boolean;
}

export interface BatchDefaults {
  default_stagger_minutes: number;
  max_videos: number;
  max_clips_per_video: number;
}

export interface MetaResponse {
  channels: Channel[];
  runs_count: number;
  batch_defaults: BatchDefaults;
}

export interface RunEvent {
  id: number;
  stage: string;
  message: string;
}

export interface Upload {
  platform: string;
  status: string;
  url?: string | null;
  error_message?: string | null;
}

export interface Run {
  run_id: string;
  topic: string;
  status: string;
  current_stage: string | null;
  trigger_source: string;
  target_platforms: string;
  source_type?: string;
  clip_path?: string | null;
  metadata_title?: string | null;
  metadata_description?: string | null;
  metadata_hashtags?: string | null;
  error_message?: string | null;
  scheduled_upload_at?: string | null;
  requested_privacy?: string | null;
  effective_privacy?: string | null;
  created_at: string;
  [key: string]: unknown;
}

export interface RunDetailResponse {
  run: Run;
  events: RunEvent[];
  uploads: Upload[];
}

export interface RunsListResponse {
  runs: Run[];
}

export interface Batch {
  batch_id: string;
  topic: string;
  status: string;
  videos_count: number;
  clips_per_video: number;
  stagger_gap_minutes: number;
  target_platforms: string;
  // Only present on GET /api/batches (list) - api_batches.py splits
  // target_platforms into this array server-side there. GET /api/batches/{id}
  // does not add it, so callers of that endpoint should fall back to
  // platformsFromStr(target_platforms) instead.
  platforms?: string[];
  error_message?: string | null;
  created_at: string;
  [key: string]: unknown;
}

export interface BatchClip {
  run_id: string;
  video_rank: number;
  clip_rank: number;
  metadata_title?: string | null;
  status: string;
  scheduled_upload_at?: string | null;
}

export interface BatchDetailResponse {
  batch: Batch;
  clips: BatchClip[];
}

export interface ScheduleEntry {
  id: number;
  topic: string;
  recurrence: string;
  scheduled_time?: string | null;
  daily_time?: string | null;
  target_platforms: string;
  status: string;
  last_run_id?: string | null;
}

// Mirrors runs_repo.platforms_from_str exactly: target_platforms is stored
// server-side as a plain comma-joined string (not JSON).
export function platformsFromStr(value: string | undefined | null): string[] {
  if (!value) return [];
  return value.split(",").filter(Boolean);
}
