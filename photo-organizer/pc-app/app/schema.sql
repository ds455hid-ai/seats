-- PC側解析アプリ SQLiteスキーマ
-- 注意: 写真・動画の内容そのものは一切保存しない。パス・数値メタデータ・ハッシュのみ。

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    absolute_path TEXT NOT NULL UNIQUE,
    relative_path TEXT NOT NULL,
    root_folder TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo', 'video')),
    extension TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    fs_created_at TEXT,
    fs_modified_at TEXT,
    captured_at TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    duration_seconds REAL,
    fps REAL,
    bitrate INTEGER,
    codec TEXT,
    latitude REAL,
    longitude REAL,
    camera_make TEXT,
    camera_model TEXT,
    orientation INTEGER,
    exif_json TEXT,
    is_screenshot INTEGER,
    screenshot_confidence REAL,
    category_guess TEXT,
    category_confidence REAL,
    blur_variance REAL,
    brightness_mean REAL,
    is_corrupt INTEGER NOT NULL DEFAULT 0,
    is_screen_recording INTEGER,
    screen_recording_confidence REAL,
    phash TEXT,
    dhash TEXT,
    quality_flags_json TEXT,
    metadata_errors_json TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'pending' CHECK (analysis_status IN ('pending', 'analyzed', 'failed')),
    analysis_error TEXT,
    scan_mtime REAL NOT NULL,
    scan_size INTEGER NOT NULL,
    scanned_at TEXT NOT NULL,
    analyzed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_media_sha256 ON media_items(sha256);
CREATE INDEX IF NOT EXISTS idx_media_captured_at ON media_items(captured_at);
CREATE INDEX IF NOT EXISTS idx_media_analysis_status ON media_items(analysis_status);
CREATE INDEX IF NOT EXISTS idx_media_type ON media_items(media_type);

CREATE TABLE IF NOT EXISTS duplicate_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT NOT NULL UNIQUE,
    item_count INTEGER NOT NULL,
    total_size INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS duplicate_group_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
    media_id INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    is_keep_recommended INTEGER NOT NULL DEFAULT 0,
    user_decision TEXT CHECK (user_decision IN ('keep', 'delete') OR user_decision IS NULL),
    UNIQUE (group_id, media_id)
);

CREATE TABLE IF NOT EXISTS similarity_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_type TEXT NOT NULL CHECK (group_type IN ('photo', 'video')),
    method TEXT NOT NULL,
    representative_media_id INTEGER REFERENCES media_items(id) ON DELETE SET NULL,
    item_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS similarity_group_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES similarity_groups(id) ON DELETE CASCADE,
    media_id INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    distance REAL,
    is_keep_recommended INTEGER NOT NULL DEFAULT 0,
    user_decision TEXT CHECK (user_decision IN ('keep', 'delete') OR user_decision IS NULL),
    UNIQUE (group_id, media_id)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_media ON analysis_results(media_id, analysis_type);

CREATE TABLE IF NOT EXISTS delete_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL UNIQUE REFERENCES media_items(id) ON DELETE CASCADE,
    deletion_candidate_score INTEGER NOT NULL DEFAULT 0,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    user_status TEXT NOT NULL DEFAULT 'candidate' CHECK (user_status IN ('candidate', 'excluded', 'confirmed')),
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_delete_candidates_score ON delete_candidates(deletion_candidate_score DESC);
CREATE INDEX IF NOT EXISTS idx_delete_candidates_status ON delete_candidates(user_status);

CREATE TABLE IF NOT EXISTS video_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    frame_index INTEGER NOT NULL,
    position_ratio REAL NOT NULL,
    thumbnail_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (media_id, frame_index)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    target_root TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_files INTEGER NOT NULL DEFAULT 0,
    processed_files INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 操作ログ: 件数・日時のみ。写真/動画の内容やサムネイルは保存しない。
CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}'
);
