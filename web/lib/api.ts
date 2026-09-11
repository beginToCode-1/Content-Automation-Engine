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

// ---------- Auth token plumbing ----------
//
// Every backend route except /api/auth/register, /api/auth/login, /api/health,
// and /media/* now requires "Authorization: Bearer <jwt>". The token is held
// here as a module-level variable, read synchronously by every apiFetch()
// call (the sole place a request leaves this app - every page/component that
// used to call fetch(apiUrl(...)) directly now goes through apiFetch() too,
// specifically so this is the only place that needs to know about auth), and
// mirrored into localStorage so a page refresh doesn't lose it. lib/auth.tsx's
// AuthProvider is the only thing that calls setAuthToken() - components should
// go through its useAuth() hook instead of touching this module directly.
const TOKEN_STORAGE_KEY = "auth_token";

let authToken: string | null =
  typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_STORAGE_KEY) : null;

export function getAuthToken(): string | null {
  return authToken;
}

export function setAuthToken(token: string | null): void {
  authToken = token;
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // localStorage unavailable (private browsing, etc.) - token still held in memory for this tab.
  }
}

// AuthProvider registers a callback here so a 401 received mid-session (an
// expired token, 7-day TTL) can clear auth state and bounce to /login from
// wherever apiFetch happens to be called, without every call site having to
// handle that itself. Only fires when a request that *had* a token comes back
// 401 - a plain wrong-password 401 from /api/auth/login has no token to begin
// with, so it flows back to the caller as a normal ApiError instead.
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (authToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const res = await fetch(apiUrl(path), { ...init, headers });
  if (!res.ok) {
    if (res.status === 401) {
      const hadToken = !!authToken;
      setAuthToken(null);
      if (hadToken && onUnauthorized) onUnauthorized();
    }
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

// Per-user, multi-account platform OAuth connections (currently YouTube
// only - see GET /api/accounts). `account_label` is the human-readable name
// (e.g. the YouTube channel title) to show as the primary label; `id` is
// what gets sent back as e.g. `youtube_account_id` on the four endpoints
// that accept a platforms list.
export interface Account {
  id: string;
  platform: string;
  account_label: string;
  external_account_id: string;
  created_at: string;
}
