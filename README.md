# Content Automation Engine

Given a topic, this tool searches YouTube for a relevant source video, downloads it,
picks the most relevant ~30-60s segment (via transcript keyword scoring), reformats it
into a vertical 9:16 clip with burned-in captions, generates title/description/hashtags
with Gemini, and uploads the result to YouTube as a Short. It can be run from the CLI
for one-off topics, or from a local web dashboard with run history and scheduling.

**Known risk**: this repurposes downloaded YouTube footage directly. That can trigger
YouTube Content ID claims or ToS enforcement on the uploading channel. Uploads default
to `private` so nothing goes live without you reviewing it first - including scheduled
runs, which are always forced to `private` regardless of any other setting.

## 1. Prerequisites setup (one-time)

### Google Cloud + YouTube Data API v3

1. Go to https://console.cloud.google.com/ and create a project.
2. **APIs & Services -> Library** -> search "YouTube Data API v3" -> Enable.
3. **APIs & Services -> OAuth consent screen** -> User type "External" -> fill in app
   name/support email -> leave publish status as "Testing" and add your own Google
   account under **Test users** (this avoids Google's app review process).
4. **APIs & Services -> Credentials -> Create Credentials -> OAuth client ID** ->
   Application type **Desktop app** -> download the JSON.
5. Save that file as `config/client_secret.json` (already gitignored).

The first real run will open a browser once to complete the OAuth consent flow, then
cache a refresh token at `config/token.json` so you won't need to repeat this.

**Quota**: default is 10,000 units/day. Search costs 100 units, upload costs 1600
units per run, so budget for roughly 5 full runs/day on the free tier.

### ffmpeg

```powershell
winget install Gyan.FFmpeg
```

Open a **new** PowerShell window afterward and confirm:

```powershell
ffmpeg -version
ffprobe -version
```

### Instagram (Reels via Instagram Graph API) - optional

1. Go to https://developers.facebook.com/ -> **My Apps -> Create App** (type: Business).
2. Add the **Instagram** product to the app, using the **Instagram API with Instagram
   Login** setup (Meta's current recommended path).
3. Convert/connect your Instagram account to a **Professional (Business or Creator)**
   account if it isn't already (Instagram app -> Settings -> Account type).
4. Under the app's Instagram product, generate a token with the
   `instagram_business_basic` and `instagram_business_content_publish` scopes, then
   exchange it for a **long-lived token** (Meta's token pages walk through this).
5. Note your Instagram professional account's numeric ID (shown in the same dashboard).
6. Instagram's API fetches the video **from a URL** - it cannot see a file on your
   machine. Run a tunnel pointed at the dashboard (which serves the clip at
   `/media/<run_id>/clip.mp4`), e.g.:
   ```powershell
   ngrok http 8000
   ```
   Keep this tunnel (and `python dashboard.py`) running for the duration of any
   Instagram upload, even for CLI-triggered runs.
7. Fill in `.env`: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`,
   `INSTAGRAM_PUBLIC_VIDEO_BASE_URL` (your tunnel's HTTPS base, e.g.
   `https://abcd1234.ngrok.io`).

**Test against a throwaway Instagram Business account first** - Instagram has no
platform-enforced "private by default" backstop like TikTok does (see below), so a
misconfigured run could actually publish. Only point `INSTAGRAM_BUSINESS_ACCOUNT_ID`
at a real account once you've verified the flow once on a test one.

### TikTok (Content Posting API) - optional

1. Go to https://developers.tiktok.com/ -> register an app with the **Content Posting
   API** product and `video.publish` scope.
2. Add an HTTPS redirect URI to the app (TikTok requires HTTPS - a plain
   `http://localhost` loopback like Google's flow won't work). The same `ngrok http
   8000` tunnel from the Instagram setup works fine for this too, e.g.
   `https://abcd1234.ngrok.io/tiktok-callback` (the path doesn't need to exist - you
   copy the code out of the browser's address bar manually, see below).
3. Fill in `.env`: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.
4. Run the one-time authorization helper, using the same redirect URI you registered:
   ```powershell
   python run.py --tiktok-auth https://abcd1234.ngrok.io/tiktok-callback
   ```
   It prints an authorization URL - open it, approve access, and you'll be redirected
   to a URL that 404s (that's fine, the tunnel doesn't need to actually handle it) but
   contains `?code=...` in the address bar. Copy that `code` value and paste it back
   into the terminal prompt. The resulting token is cached at
   `config/tiktok_token.json` (gitignored) and refreshed automatically after that.

**This is inherently low-risk to test for real**: TikTok itself restricts an
unaudited app to posting privately/as a draft visible only to your own account, so
there's no way for a test upload to go public by accident.

### Python environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked by execution policy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Secrets

```powershell
copy .env.example .env
```

Then fill in `.env`:

- `GEMINI_API_KEY` - required, used to generate title/description/hashtags. Get a free
  key (no billing needed for the free tier) at https://aistudio.google.com/apikey.
- `YOUTUBE_API_KEY` - optional. If set, search uses this API key (no OAuth prompt
  needed for search). Upload always requires OAuth regardless.
- `UPLOAD_PRIVACY_STATUS` - defaults to `private`. Change to `public` only once
  you've verified output quality.
- `DASHBOARD_HOST` / `DASHBOARD_PORT` / `DASHBOARD_MAX_WORKERS` / `DB_PATH` /
  `SCHEDULER_POLL_INTERVAL_S` - dashboard settings, sensible defaults provided.
- `INSTAGRAM_*` / `TIKTOK_*` - optional, only needed if you want those platforms.
  See the Instagram/TikTok setup sections above.

## 2. Verifying setup

```powershell
python run.py --check-setup
```

Confirms `.env`, ffmpeg, and OAuth credentials are all in place, and makes one
trivial YouTube search call to confirm API access actually works.

## 3. Running from the CLI

Dry run first (generates the clip and metadata, skips uploading):

```powershell
python run.py --topic "stoic philosophy" --dry-run
```

Check the printed `work/<run_id>/clip_captioned.mp4` path - open it and confirm the
source video, segment choice, vertical framing, and captions look right.

Once satisfied, run for real (uploads as `private` by default):

```powershell
python run.py --topic "stoic philosophy"
```

Check YouTube Studio -> Content for the uploaded Short. Verify metadata and watch
for any Content ID claim before manually flipping it to public.

Upload to multiple platforms at once with `--platforms` (default is `youtube` only):

```powershell
python run.py --topic "stoic philosophy" --platforms youtube tiktok
```

## 4. Running the dashboard

```powershell
python dashboard.py
```

Opens a local web server (default http://127.0.0.1:8000, binds to localhost only):

- **`/`** - start a new run (topic, platforms, generate-only vs. generate+upload) and
  see recent run history with live status.
- **`/runs/{id}`** - live stage-by-stage progress, clip preview, generated metadata,
  and per-platform upload status for one run.
- **`/schedule`** - schedule a topic to run automatically, once at a specific time or
  daily at a given time. Scheduled runs always upload as `private` - there is no way
  to configure a public scheduled upload, by design.

Run history and schedules persist in a local SQLite file (`content_engine.db` by
default, gitignored). The dashboard survives being killed mid-run: any run still
`pending`/`running` at startup is marked `failed` (no silent stuck runs), though a
truly interrupted pipeline is not resumed - you just re-run that topic.

## 5. Cloud deployment (backend + web frontend)

The app is split into two deployable pieces:

- **Backend** (`content_engine/`, this repo's root) - the FastAPI API, scheduler,
  downloader, renderer, and uploaders. This does real work (ffmpeg, background
  polling, file storage) and needs a host that runs a persistent process, not
  serverless functions. Deploy it to **Railway** or **Render**.
- **Frontend** (`web/`) - a standalone Next.js dashboard that talks to the backend
  purely over its `/api/*` JSON endpoints and `/media/*` clip files. Deploy it to
  **Vercel**.

### Backend -> Railway or Render

A `Dockerfile` (installs `ffmpeg`) and `render.yaml` blueprint are included at the
repo root.

**Render**: Dashboard -> New -> Blueprint -> pick this repo -> it reads
`render.yaml` automatically (a Docker web service on the **free** plan, health
check at `/api/health`). Fill in the `sync: false` env vars it prompts for
(`GEMINI_API_KEY` at minimum). Under **Settings -> Environment**, upload
`config/client_secret.json` and `config/token.json` as **Secret Files** - the
app reads them from `config/` at runtime and they're gitignored, so they must
be uploaded directly through the host's dashboard, not committed.

The free plan has no persistent disk: `work/` and the SQLite DB live in the
container's own ephemeral filesystem and reset on every restart/redeploy, and
the instance spins down after 15 minutes idle (a ~30-60s cold start on the
next request). Fine for trying the deploy out. For real ongoing use, upgrade
the service to a paid plan, attach a Render **Disk** mounted at `/data`, and
set `WORK_DIR=/data/work` / `DB_PATH=/data/content_engine.db` so runs and
history actually persist.

**Railway**: New Project -> Deploy from GitHub repo -> it detects the `Dockerfile`.
Add a **Volume** mounted at `/data`. Set the same env vars as above, plus
`WORK_DIR=/data/work` and `DB_PATH=/data/content_engine.db`.

Either way, once deployed, set `CORS_ALLOW_ORIGINS` on the backend to your Vercel
frontend's URL (e.g. `https://your-app.vercel.app`) so the browser is allowed to
call it cross-origin.

### Frontend -> Vercel

```powershell
cd web
npm install
```

Import the repo on https://vercel.com/new, set **Root Directory** to `web`, and add
the project env var `NEXT_PUBLIC_API_BASE_URL` pointing at your deployed backend
URL (e.g. `https://your-backend.onrender.com`). See `web/README.md` for local dev.

### Note on persistence

Downloaded videos, rendered clips, and the SQLite database live on disk. On
Railway/Render this only survives redeploys if you attach a persistent volume/disk
(as configured above) - without one, `work/` and the DB reset on every deploy.

## Project layout

```
run.py                      CLI entrypoint
dashboard.py                 Dashboard entrypoint (python dashboard.py)
content_engine/
  config.py                 .env loading/validation
  models.py                 shared dataclasses
  errors.py                 one exception type per pipeline stage
  scoring.py                shared TF-IDF relevance scorer
  pipeline.py                orchestrates the stages below, in order
  search/                   YouTube search + best-candidate selection
  download/                 yt-dlp video download
  transcript/                transcript fetch + best-segment selection
  render/                    ffmpeg: cut -> vertical reformat -> burned-in captions
  metadata/                  Gemini-generated title/description/hashtags
  auth/                     Google OAuth + TikTok OAuth flows, token caching
  uploaders/                 YouTube, Instagram, and TikTok uploaders
  db/                        SQLite schema + repos (runs, run_events, run_uploads, scheduled_topics)
  webapp/                    FastAPI app, background executor, scheduler, routes, templates
tests/                       unit tests (segment selection, ffmpeg, DB repos, pipeline, scheduler, uploaders)
```

## Running tests

```powershell
python -m pytest
```

## What's deliberately not built yet

- True mid-run cancellation (only a run that hasn't started executing yet can be
  cancelled from the dashboard; a running pipeline runs to completion)
- Multi-video compilation (single video, single segment only)
- Upload retry logic (a failed/rejected upload is a terminal error per run, by design)
- Speech-to-text fallback for videos with no captions at all
- Multi-user auth on the dashboard (single-user local tool, binds to 127.0.0.1 by default)
- Chunked multi-part TikTok upload (single-chunk only, fine for our ~30-60s clips;
  a clip over 50MB will fail with a clear error rather than silently truncating)
- Automated tunnel management for Instagram/TikTok (you run `ngrok` yourself)
- Full TikTok public posting (gated on TikTok's own app-review process)
