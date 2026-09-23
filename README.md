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

### YouTube: per-user "Connect Account" flow (web dashboard)

The CLI (above) uses one shared account for the whole machine. The web dashboard is
different: **each logged-in user connects their own YouTube channel(s)** from a
"Connected Accounts" page, and can connect more than one and pick which to publish to
per run. This needs a **separate, second OAuth client** - a "Web application" type,
not the "Desktop app" one above:

1. **APIs & Services -> Credentials -> Create Credentials -> OAuth client ID** ->
   Application type **Web application**.
2. **Authorized redirect URIs** -> add your backend's callback URL, e.g.
   `https://your-backend.onrender.com/api/oauth/youtube/callback` (and
   `http://127.0.0.1:8000/api/oauth/youtube/callback` for local dev).
3. Fill in `.env` / your host's env vars: `GOOGLE_OAUTH_CLIENT_ID`,
   `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` (must exactly match what
   you entered in step 2), and `FRONTEND_BASE_URL` (your deployed frontend's origin -
   where the browser lands after a connect attempt finishes).
4. Under **OAuth consent screen -> Test users**, add the Google account(s) of every
   person who should be able to connect a channel. **This app stays in Google's
   "Testing" mode** - up to 100 manually-added test users, no public app review. Anyone
   not added here gets rejected by Google at the consent screen, regardless of whether
   they have an account on this app.
5. `TOKEN_ENCRYPTION_KEY` (also required) encrypts stored per-account tokens at rest -
   generate with:
   ```
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

Leave `GOOGLE_OAUTH_CLIENT_ID`/`_SECRET`/`_REDIRECT_URI` unset to disable the connect
flow entirely (the rest of the app keeps working; "Connect YouTube" just 400s).

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
   machine. Two ways to give it one:
   - **Automatic (recommended for local dev)**: set `NGROK_AUTHTOKEN` in `.env` (a
     free ngrok account's token, from https://dashboard.ngrok.com/get-started/your-authtoken)
     and the dashboard starts a tunnel to itself automatically on boot - no
     `INSTAGRAM_PUBLIC_VIDEO_BASE_URL` needed. A fresh ngrok URL each restart is fine
     here, since Instagram just fetches whatever URL is live at upload time.
   - **Manual**: run a tunnel yourself and set the URL explicitly:
     ```powershell
     ngrok http 8000
     ```
     Keep this tunnel (and `python dashboard.py`) running for the duration of any
     Instagram upload, even for CLI-triggered runs.
7. Fill in `.env`: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`, and
   either `NGROK_AUTHTOKEN` (automatic tunnel) or `INSTAGRAM_PUBLIC_VIDEO_BASE_URL`
   (manual tunnel's HTTPS base, e.g. `https://abcd1234.ngrok.io`) - an explicit
   `INSTAGRAM_PUBLIC_VIDEO_BASE_URL` always wins if both are set.

**Test against a throwaway Instagram Business account first** - Instagram has no
platform-enforced "private by default" backstop like TikTok does (see below), so a
misconfigured run could actually publish. Only point `INSTAGRAM_BUSINESS_ACCOUNT_ID`
at a real account once you've verified the flow once on a test one.

### TikTok (Content Posting API) - optional

1. Go to https://developers.tiktok.com/ -> register an app with the **Content Posting
   API** product and `video.publish` scope.
2. Add an HTTPS redirect URI to the app (TikTok requires HTTPS - a plain
   `http://localhost` loopback like Google's flow won't work), e.g.
   `https://abcd1234.ngrok.io/tiktok-callback` (the path doesn't need to exist - you
   copy the code out of the browser's address bar manually, see below).
3. Fill in `.env`: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.
4. Run the one-time authorization helper, using the same redirect URI you registered:
   ```powershell
   python run.py --tiktok-auth https://abcd1234.ngrok.io/tiktok-callback
   ```
   If `NGROK_AUTHTOKEN` is set in `.env`, this starts a tunnel for you automatically
   and prints its URL - otherwise run `ngrok http 8000` yourself first, same as before.
   Either way, **the printed/tunnel URL has to match what's registered in step 2** -
   ngrok's free tier gives a new random URL every time it starts, so if it's
   different from last time, update the redirect URI in TikTok's developer dashboard
   before continuing (a paid ngrok reserved domain avoids this, but isn't required).
   The command then prints an authorization URL - open it, approve access, and
   you'll be redirected to a URL that 404s (that's fine, the tunnel doesn't need to
   actually handle it) but contains `?code=...` in the address bar. Copy that `code`
   value and paste it back into the terminal prompt. The resulting token is cached
   at `config/tiktok_token.json` (gitignored) and refreshed automatically after that.

**This is inherently low-risk to test for real**: TikTok itself restricts an
unaudited app to posting privately/as a draft visible only to your own account, so
there's no way for a test upload to go public by accident.

### Postgres (Supabase)

The app stores users, run history, schedules, and connected accounts in
Postgres - there is no local database file. Two separate projects are
recommended: one for local development/tests, one for production, so the
test suite (which truncates its tables before every test) never touches
real data.

1. Sign up free at https://supabase.com and create a project (e.g.
   `content-engine-dev`). Repeat for a second project (e.g.
   `content-engine-prod`) if you want separate dev/prod databases.
2. For each project: **Connect** (top of the project dashboard) -> **Direct
   Connection** -> **Session pooler** tab -> copy the connection URI.
   Use the **Session pooler**, not Transaction pooler - this app holds its
   own persistent connection pool rather than opening brief per-request
   connections, and Transaction-mode pooling disables prepared statements,
   which the Python Postgres driver enables by default after a few repeated
   queries.
3. Replace `[YOUR-PASSWORD]` in the URI with that project's database
   password (set when you created the project; reset it under **Project
   Settings -> Database** if you've lost it), and append `?sslmode=require`.
4. Put the dev project's URI in `.env` as `DATABASE_URL` (see Secrets below).
   Keep the prod project's URI aside for the Render deployment step - it
   doesn't need to go into `.env` or git.

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
- `DATABASE_URL` - required. A Postgres connection string. For Supabase, use
  the **Session pooler** URI (Project Settings -> Database -> Connect ->
  Direct Connection -> Session pooler) - not Transaction pooler, since this
  app holds its own persistent connection pool and Transaction-mode pooling
  disables prepared statements. Append `?sslmode=require`.
- `DASHBOARD_HOST` / `DASHBOARD_PORT` / `DASHBOARD_MAX_WORKERS` /
  `SCHEDULER_POLL_INTERVAL_S` - dashboard settings, sensible defaults provided.
- `INSTAGRAM_*` / `TIKTOK_*` - optional, only needed if you want those platforms.
  See the Instagram/TikTok setup sections above.
- `NGROK_AUTHTOKEN` - optional. If set (and this isn't a deployed/`PORT`-injected
  environment), the dashboard automatically starts an ngrok tunnel to itself on
  boot, for Instagram uploads and the TikTok auth helper - see the Instagram/TikTok
  setup sections above. Leave unset to keep running `ngrok` yourself.
- `UPLOAD_MAX_RETRIES` / `UPLOAD_RETRY_BACKOFF_BASE_S` - defaults `3` / `2`. Transient
  upload failures (network blips, timeouts, 5xx/429 responses) are retried with
  exponential backoff before the run is marked failed; non-transient failures (bad
  credentials, rejected content) are never retried.
- `JWT_SECRET_KEY` - required, signs login sessions. Generate one with
  `python -c "import secrets; print(secrets.token_hex(32))"` - never reuse the
  same value across environments, and never commit a real one.

### Authentication and roles

Every API route except `/api/auth/register`, `/api/auth/login`, `/api/health`,
and the media file endpoint requires a logged-in user. There is no separate
admin-invite flow: **the first account ever registered on a given database
becomes `admin`**; every account after that defaults to `viewer`. Register
the first (admin) account for yourself immediately after deploying, before
sharing the URL with anyone else.

- **admin** - full access: start runs/batches, manage schedules, retry/cancel,
  self-upload and publish.
- **viewer** - read-only: browse run/batch/schedule history, watch clips,
  inspect metadata. Cannot trigger anything that costs API quota or publishes
  content.

Data is per-user: each account only sees the runs/batches/schedules it
created, regardless of role. There's no cross-user visibility (an admin
doesn't see a viewer's data or vice versa). An admin can promote/demote any
account from the **Users** page (admin-only). A role change takes effect the
next time that account logs in - it's embedded in the login JWT, not
re-checked against the database on every request.

### Connected YouTube accounts

Each admin connects their own YouTube channel(s) from the Connected Accounts page
(see the "YouTube: per-user Connect Account flow" setup section above) and can
connect more than one. When starting a run/batch/schedule/self-upload that includes
`youtube` as a target platform:
- Exactly one connected account -> used automatically.
- Zero connected accounts -> the request 400s with "Connect a YouTube account first".
- Two or more -> the request must specify `youtube_account_id` explicitly, or it 400s.

Tokens are encrypted at rest (`TOKEN_ENCRYPTION_KEY`) and refreshed automatically when
expired. Instagram/TikTok are **not** on this per-user model yet - they're still one
shared credential set for the whole deployment, configured via `.env`/host env vars.

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

Run history and schedules persist in Postgres (`DATABASE_URL`), not a local file -
see the Postgres setup below. The dashboard survives being killed mid-run: any run still
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

Set `DATABASE_URL` to your **`content-engine-prod`** Supabase project's Session
pooler connection string (see the Postgres setup above) - never the dev one.
User accounts, run history, and schedules live there and survive restarts,
redeploys, and the free plan's idle spin-down (a ~30-60s cold start on the
next request after 15 minutes idle - normal, not a bug). The free plan still
has no persistent *disk*, though: `work/` (downloaded videos, rendered clips)
lives in the container's own ephemeral filesystem and resets on every
restart/redeploy. Fine for trying the deploy out; for real ongoing use,
upgrade the service to a paid plan, attach a Render **Disk** mounted at
`/data`, and set `WORK_DIR=/data/work` so in-progress clip files survive too.

**Railway**: New Project -> Deploy from GitHub repo -> it detects the `Dockerfile`.
Set the same env vars as above. Add a **Volume** mounted at `/data` and set
`WORK_DIR=/data/work` if you also want clip files to survive redeploys.

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

User accounts, run history, and schedules live in Postgres (`DATABASE_URL`)
and survive redeploys regardless of disk configuration. Downloaded videos and
rendered clips (`work/`) live on the container's local disk - on Railway/Render
this only survives redeploys if you attach a persistent volume/disk (as
configured above); without one, `work/` resets on every deploy.

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
  uploaders/                 YouTube, Instagram, and TikTok uploaders (with retry/backoff)
  tunnel.py                 optional automatic ngrok tunnel (NGROK_AUTHTOKEN), local dev only
  db/                        Postgres schema + connection pool + repos (users, runs, run_events, run_uploads, scheduled_topics, connected_accounts)
  db/migrations/             numbered, version-tracked schema migrations, applied on every boot
  webapp/                    FastAPI app, background executor, scheduler, routes, templates
tests/                       unit tests (segment selection, ffmpeg, DB repos, pipeline, scheduler, uploaders)
```

## Running tests

Needs `DATABASE_URL` set (see Postgres setup above) - the suite truncates its
tables before every test that touches the database, so point it at your dev
project, never production.

```powershell
python -m pytest
```

## What's deliberately not built yet

- Multi-video compilation (single video, single segment only)
- Speech-to-text fallback for videos with no captions at all
- Per-user Instagram/TikTok accounts (still one shared credential set per deployment)
- Chunked multi-part TikTok upload (single-chunk only, fine for our ~30-60s clips;
  a clip over 50MB will fail with a clear error rather than silently truncating)
- TikTok's redirect-URI re-registration when the ngrok tunnel URL changes (a TikTok
  platform constraint - it requires a pre-registered URI, and only a paid ngrok
  reserved domain avoids the tunnel URL changing on restart; see the TikTok setup
  section above)
- Full TikTok public posting (gated on TikTok's own app-review process)
- Batch run cancellation (mid-run cancellation covers single runs only, not batches)
- An audit trail for role changes (who promoted/demoted whom, and when)
