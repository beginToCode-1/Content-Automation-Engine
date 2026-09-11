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
