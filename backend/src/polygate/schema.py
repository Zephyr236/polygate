"""SQLite schema shared by the metrics store and admin auth tables."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL,
    model TEXT NOT NULL,
    at REAL NOT NULL,
    ok INTEGER NOT NULL,
    error_class TEXT,
    latency_ms REAL NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    reasoning_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    cost REAL NOT NULL,
    switched INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_at ON metrics(at);
CREATE INDEX IF NOT EXISTS idx_metrics_provider ON metrics(provider_id, at);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    kind TEXT NOT NULL,
    provider_id TEXT,
    detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_password (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    allowed_providers TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    last_used_at REAL,
    revoked_at REAL
);
"""
