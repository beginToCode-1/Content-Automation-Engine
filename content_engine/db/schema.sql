CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    trigger_source TEXT NOT NULL CHECK(trigger_source IN ('cli','web','scheduled')),
    schedule_id INTEGER REFERENCES scheduled_topics(id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','failed')),
    current_stage TEXT,
    dry_run INTEGER NOT NULL DEFAULT 0,
    requested_privacy TEXT,
    effective_privacy TEXT,
    target_platforms TEXT NOT NULL DEFAULT 'youtube',
    source_video_id TEXT,
    source_video_title TEXT,
    source_video_url TEXT,
    segment_start_s REAL,
    segment_end_s REAL,
    segment_score REAL,
    clip_path TEXT,
    metadata_title TEXT,
    metadata_description TEXT,
    metadata_hashtags TEXT,
    error_message TEXT,
    work_dir TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    started_at TEXT,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_status_created ON runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    stage TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id, id);

CREATE TABLE IF NOT EXISTS run_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    platform TEXT NOT NULL CHECK(platform IN ('youtube','instagram','tiktok')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','uploading','succeeded','failed','skipped')),
    video_id TEXT,
    url TEXT,
    privacy_status TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    finished_at TEXT,
    UNIQUE(run_id, platform)
);

CREATE TABLE IF NOT EXISTS scheduled_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    recurrence TEXT NOT NULL DEFAULT 'once' CHECK(recurrence IN ('once','daily')),
    scheduled_time TEXT,
    daily_time TEXT,
    target_platforms TEXT NOT NULL DEFAULT 'youtube',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled','completed')),
    last_triggered_at TEXT,
    last_run_id TEXT REFERENCES runs(run_id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_schedules_status ON scheduled_topics(status);

CREATE TABLE IF NOT EXISTS run_batches (
    batch_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    target_platforms TEXT NOT NULL,
    videos_count INTEGER NOT NULL,
    clips_per_video INTEGER NOT NULL,
    stagger_gap_minutes INTEGER NOT NULL,
    requested_privacy TEXT,
    status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','succeeded','failed')),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    finished_at TEXT
);
