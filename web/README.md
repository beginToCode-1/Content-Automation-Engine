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
  draft+publish flow) for a `viewer`-role user via `const isAdmin = user?.role === "admin"` checks in the relevant
  pages, as a UX nicety on top of that server-side boundary.
