# Content Engine - Web Frontend

A standalone Next.js (App Router, TypeScript) frontend for Content Automation Engine. It is a faithful port of
the server-rendered Jinja2/vanilla-JS dashboard at `content_engine/webapp/` - same layout, same CSS
(`app/globals.css` is a verbatim copy of `content_engine/webapp/static/style.css`), same client-side behavior -
rebuilt as a client-rendered React app that talks to the FastAPI backend purely over its JSON `/api/*` endpoints
and its `/media/{run_id}/clip.mp4` file endpoint.

This app has no server-side data access of its own (no DB, no filesystem access to render jobs) - every page
fetches from the backend on mount and shows a brief loading state first. The Python backend's own Jinja UI keeps
working unmodified as a fallback; this is the new deployable-to-Vercel frontend for it.

## Setup

```bash
npm install
cp .env.local.example .env.local
# edit .env.local if your backend isn't running on http://localhost:8000
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend (`content_engine.webapp`, e.g. via
`uvicorn content_engine.webapp.app:app --reload`) must be running and reachable at the URL configured in
`NEXT_PUBLIC_API_BASE_URL` - by default `http://localhost:8000`. CORS is already enabled server-side for this.

## Build

```bash
npm run build
```

## Deploy

Deploy this `web/` directory to Vercel as its own project (set Vercel's "Root Directory" to `web`). Set the
`NEXT_PUBLIC_API_BASE_URL` environment variable in the Vercel project settings to the URL of your deployed backend
(Railway/Render), e.g. `https://your-backend.up.railway.app`. It must be set at build time since it's inlined into
the client bundle as a `NEXT_PUBLIC_*` variable.

## Notes

- The `/batch` page's "Recent Batches" table is populated from `GET /api/batches?limit=20`, and its video/clip-count
  limits and default stagger come from `GET /api/meta`'s `batch_defaults` field. `app/batch/page.tsx` keeps small
  hardcoded fallback constants (5, 5, 180 minutes, matching `content_engine/config.py`'s defaults) that are only
  used for the brief moment before that `/api/meta` fetch resolves.

## Connected Accounts (per-user YouTube OAuth)

Each user connects their own YouTube channel(s) - there is no more shared/global YouTube credential.

- `app/accounts/page.tsx` (linked from the sidebar as "Connected Accounts") lists the current user's connected
  accounts (`GET /api/accounts`), lets an admin disconnect one (`DELETE /api/accounts/{id}`, with a
  `window.confirm` first), and has a "Connect YouTube" button.
- Connecting is **not** a normal `apiFetch()` call: clicking "Connect YouTube" does a full browser navigation
  (`window.location.href = ${apiUrl("/api/oauth/youtube/connect")}?token=${token}`) because Google's consent screen
  redirects back to the backend's own callback, so there is no way to attach a fetch `Authorization` header the way
  the rest of the app does. The backend then redirects the browser back to `/accounts?connected=youtube` on
  success or `/accounts?error=<reason>` on failure; the page reads those via `useSearchParams()` (wrapped in a
  `<Suspense>` boundary) on mount, shows a one-time dismissible banner using the existing `.info-banner` style, and
  strips the query params from the URL afterward.
- A viewer-role user can see the read-only account list but not the "Connect YouTube"/"Disconnect" buttons -
  connected accounts are tied to the connecting admin's own Google credential and affect who a run can publish as,
  so this follows the same "admin has full access, viewer is read-only" convention as the rest of the app.
- `components/YouTubeAccountPicker.tsx` is a shared component used by all four forms that can target YouTube
  (`app/studio/page.tsx`, `app/batch/page.tsx`, `app/schedule/page.tsx`, and the self-upload publish step in
  `app/page.tsx`): when "YouTube" is checked as a target platform, it fetches `GET /api/accounts` and shows nothing
  extra with 0 accounts connected (just an inline hint linking to `/accounts` - the backend's own 400 message is
  clear enough that no client-side submit-blocking was added), a small "Publishing to: {label}" hint with exactly 1
  (auto-selected server-side either way), or a `<select>` with 2+ (defaults to no selection, forcing an explicit
  choice - the backend 400s with a clear message if `youtube_account_id` is left unset in that case). The chosen id
  is included as `youtube_account_id` in the relevant POST body only when "youtube" is checked.

## Auth

The backend requires a JWT (`Authorization: Bearer <token>`) on every route except `/api/auth/register`,
`/api/auth/login`, `/api/health`, and `/media/*`. This app wires that in as follows:

- `lib/auth.tsx` exports an `AuthProvider` (mounted in `app/layout.tsx`, wrapping the whole app) and a `useAuth()`
  hook (`{ user, token, initializing, login, register, logout }`). The token is persisted to
  `localStorage["auth_token"]` and mirrored into a module-level variable in `lib/api.ts` so it can be read
  synchronously by every `apiFetch()` call - including on first paint, before any effect has run.
- **First account ever registered on the backend becomes `role: "admin"`; every account after that defaults to
  `"viewer"`.** There is no invite flow. The signup page (`app/signup/page.tsx`) surfaces this in an info banner.
- `components/AuthGate.tsx` (rendered around `{children}` in the layout) redirects to `/login` if there's no valid
  user once the initial token check finishes, for every route except `/login`, `/signup`, `/privacy`, and `/terms`.
  It shows a brief loading state while that initial check is in flight, and bounces an already-logged-in user away
  from `/login`/`/signup` back to `/`.
- If any `apiFetch()` call gets a 401 for a request that *had* a token attached (an expired session, not a bad
  login/register attempt), `lib/api.ts` clears the stored token and `AuthProvider` redirects to `/login`.
- `admin` has full access; `viewer` is read-only. The backend enforces this server-side (403 on a viewer hitting an
  admin-only route) - the UI additionally hides or disables the corresponding controls (starting a run, retrying a
  run, cancelling a scheduled upload, creating a batch, creating/cancelling a schedule, the self-upload
  draft+publish flow, connecting/disconnecting a YouTube account) for a `viewer`-role user via
  `const isAdmin = user?.role === "admin"` checks in the relevant pages, as a UX nicety on top of that server-side
  boundary.
