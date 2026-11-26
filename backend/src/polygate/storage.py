"""SQLite-backed metrics rollups and event log for the admin dashboard."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import aiosqlite


@dataclass
class MetricRecord:
    """One completed upstream call as persisted for analytics."""

    provider_id: str
    model: str
    ok: bool
    error_class: str | None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    cost: float
    switched: int = 0
    at: float = field(default_factory=time.time)


_SCHEMA = """
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
"""


class MetricsStore:
    """Async store for call metrics, events and provider overrides."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Open the database and create the schema."""
        db = await aiosqlite.connect(self._path)
        db.row_factory = aiosqlite.Row
        await db.executescript(_SCHEMA)
        await db.commit()
        self._db = db

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def _connection(self) -> aiosqlite.Connection:
        """Return the open connection, failing loudly when the store is closed."""
        if self._db is None:  # pragma: no cover - guarded by app lifecycle
            raise RuntimeError("metrics store is not open")
        return self._db

    async def record(self, record: MetricRecord) -> None:
        """Persist one call metric."""
        async with self._lock:
            db = await self._connection()
            await db.execute(
                "INSERT INTO metrics (provider_id, model, at, ok, error_class, latency_ms, prompt_tokens,"
                " completion_tokens, reasoning_tokens, cache_read_tokens, cost, switched)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.provider_id,
                    record.model,
                    record.at,
                    int(record.ok),
                    record.error_class,
                    record.latency_ms,
                    record.prompt_tokens,
                    record.completion_tokens,
                    record.reasoning_tokens,
                    record.cache_read_tokens,
                    record.cost,
                    record.switched,
                ),
            )
            await db.commit()

    async def add_event(self, kind: str, provider_id: str | None, detail: str) -> None:
        """Append an operational event."""
        async with self._lock:
            db = await self._connection()
            await db.execute(
                "INSERT INTO events (at, kind, provider_id, detail) VALUES (?, ?, ?, ?)",
                (time.time(), kind, provider_id, detail),
            )
            await db.commit()

    async def admin_password_configured(self) -> bool:
        """Return whether the first-run admin password exists."""
        db = await self._connection()
        cursor = await db.execute("SELECT 1 FROM admin_password WHERE id = 1")
        return await cursor.fetchone() is not None

    async def get_admin_password_hash(self) -> str | None:
        """Return the stored password hash, if configured."""
        db = await self._connection()
        cursor = await db.execute("SELECT password_hash FROM admin_password WHERE id = 1")
        row = await cursor.fetchone()
        return None if row is None else str(row["password_hash"])

    async def set_admin_password(self, password_hash: str) -> bool:
        """Set the first-run password once; return False if already configured."""
        async with self._lock:
            db = await self._connection()
            cursor = await db.execute("SELECT 1 FROM admin_password WHERE id = 1")
            if await cursor.fetchone() is not None:
                return False
            await db.execute(
                "INSERT INTO admin_password (id, password_hash, updated_at) VALUES (1, ?, ?)",
                (password_hash, time.time()),
            )
            await db.commit()
            return True

    async def create_admin_session(self, token_hash: str, expires_at: float) -> None:
        """Persist a hashed browser session token."""
        async with self._lock:
            db = await self._connection()
            await db.execute(
                "INSERT INTO admin_sessions (token_hash, created_at, expires_at) VALUES (?, ?, ?)",
                (token_hash, time.time(), expires_at),
            )
            await db.commit()

    async def admin_session_valid(self, token_hash: str) -> bool:
        """Return whether a session token is present and unexpired."""
        db = await self._connection()
        cursor = await db.execute(
            "SELECT 1 FROM admin_sessions WHERE token_hash = ? AND expires_at > ?",
            (token_hash, time.time()),
        )
        return await cursor.fetchone() is not None

    async def delete_admin_session(self, token_hash: str) -> None:
        """Revoke one browser session token."""
        async with self._lock:
            db = await self._connection()
            await db.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (token_hash,))
            await db.commit()

    async def overview(self, since_seconds: float) -> list[dict[str, Any]]:
        """Return per-provider aggregates over a trailing window."""
        cutoff = time.time() - since_seconds
        db = await self._connection()
        cursor = await db.execute(
            "SELECT provider_id, COUNT(*) AS calls, SUM(ok) AS ok,"
            " SUM(1 - ok) AS failures,"
            " AVG(latency_ms) AS avg_latency, MAX(latency_ms) AS max_latency,"
            " SUM(prompt_tokens) AS prompt_tokens,"
            " SUM(completion_tokens) AS completion_tokens, SUM(reasoning_tokens) AS reasoning_tokens,"
            " SUM(cache_read_tokens) AS cache_read_tokens, SUM(cost) AS cost, SUM(switched) AS switches"
            " FROM metrics WHERE at >= ? GROUP BY provider_id",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def timeseries(self, since_seconds: float, bucket_seconds: int) -> list[dict[str, Any]]:
        """Return call counts, failures and latency per provider and time bucket."""
        cutoff = time.time() - since_seconds
        db = await self._connection()
        cursor = await db.execute(
            "SELECT provider_id, CAST(at / ? AS INTEGER) * ? AS bucket, COUNT(*) AS calls,"
            " SUM(ok) AS ok, SUM(1 - ok) AS failures, AVG(latency_ms) AS avg_latency"
            " FROM metrics WHERE at >= ? GROUP BY provider_id, bucket ORDER BY bucket",
            (bucket_seconds, bucket_seconds, cutoff),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent operational events."""
        db = await self._connection()
        cursor = await db.execute(
            "SELECT at, kind, provider_id, detail FROM events ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def save_provider(self, provider_id: str, payload: str) -> None:
        """Persist a provider config override."""
        async with self._lock:
            db = await self._connection()
            await db.execute(
                "INSERT INTO providers (id, payload, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at",
                (provider_id, payload, time.time()),
            )
            await db.commit()

    async def list_providers(self) -> list[dict[str, Any]]:
        """Return persisted provider overrides."""
        db = await self._connection()
        cursor = await db.execute("SELECT id, payload FROM providers ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_provider(self, provider_id: str) -> None:
        """Delete a persisted provider override."""
        async with self._lock:
            db = await self._connection()
            await db.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
            await db.commit()
