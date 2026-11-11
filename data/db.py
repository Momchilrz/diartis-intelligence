"""SQLite cache, schema, and timeframe queries.

`insight` and `source` sit beside the requested columns so every card can
carry an honest attribution and a creative reading of the metric.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from config import DB_PATH, SOURCE_APIFY, SOURCE_SERPER, TIMEFRAMES

SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    hex_codes TEXT NOT NULL,
    ad_format TEXT NOT NULL,
    active_days INTEGER NOT NULL,
    screenshot_url TEXT,
    timestamp TEXT NOT NULL,
    insight TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'STUDIO BASELINE'
);

CREATE TABLE IF NOT EXISTS video_hooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    hook_text TEXT NOT NULL,
    archetype TEXT NOT NULL,
    script_structure TEXT NOT NULL,
    engagement_tier TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    insight TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'STUDIO BASELINE'
);

CREATE TABLE IF NOT EXISTS domain_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    domain_name TEXT NOT NULL,
    target_keyword TEXT NOT NULL,
    rank_position INTEGER NOT NULL,
    rank_change INTEGER,
    timestamp TEXT NOT NULL,
    insight TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'STUDIO BASELINE'
);

CREATE TABLE IF NOT EXISTS copilot_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_brief TEXT NOT NULL,
    region TEXT NOT NULL,
    generated_proposal TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_visual_region_time ON visual_trends(region, timestamp);
CREATE INDEX IF NOT EXISTS idx_hooks_region_time ON video_hooks(region, timestamp);
CREATE INDEX IF NOT EXISTS idx_domains_region_time ON domain_metrics(region, timestamp);
CREATE INDEX IF NOT EXISTS idx_copilot_region_time ON copilot_history(region, timestamp);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


_TIMEFRAME_DAYS = {
    "24 Hours": 1,
    "7 Days": 7,
    "30 Days": 30,
}


def timeframe_cutoff(timeframe: str) -> str:
    if timeframe not in TIMEFRAMES or timeframe not in _TIMEFRAME_DAYS:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    moment = datetime.now(timezone.utc) - timedelta(days=_TIMEFRAME_DAYS[timeframe])
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _query(sql: str, params: tuple) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _latest_unique(rows: list[dict], keyfn) -> list[dict]:
    seen = set()
    output = []
    for row in rows:
        key = keyfn(row)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _prefer_live(rows: list[dict], live_source: str) -> list[dict]:
    live = [row for row in rows if row.get("source") == live_source]
    if live:
        return live
    return [row for row in rows if row.get("source") != live_source]


def fetch_visuals(region: str, timeframe: str) -> list[dict]:
    rows = _query(
        """
        SELECT * FROM visual_trends
        WHERE region = ? AND timestamp >= ?
        ORDER BY timestamp DESC, id DESC
        """,
        (region, timeframe_cutoff(timeframe)),
    )
    for row in rows:
        row["hex_codes"] = _loads(row.get("hex_codes"), [])
    return _latest_unique(rows, lambda row: row.get("ad_format"))


def fetch_hooks(region: str, timeframe: str) -> list[dict]:
    rows = _query(
        """
        SELECT * FROM video_hooks
        WHERE region = ? AND timestamp >= ?
        ORDER BY timestamp DESC, id DESC
        """,
        (region, timeframe_cutoff(timeframe)),
    )
    for row in rows:
        row["script_structure"] = _loads(row.get("script_structure"), {})
    rows = _prefer_live(rows, SOURCE_APIFY)
    return _latest_unique(rows, lambda row: row.get("hook_text"))


def fetch_domains(region: str, timeframe: str) -> list[dict]:
    rows = _query(
        """
        SELECT * FROM domain_metrics
        WHERE region = ? AND timestamp >= ?
        ORDER BY timestamp DESC, id DESC
        """,
        (region, timeframe_cutoff(timeframe)),
    )
    rows = _prefer_live(rows, SOURCE_SERPER)
    return _latest_unique(rows, lambda row: (row.get("domain_name"), row.get("target_keyword")))


def latest_cache_time(region: str) -> datetime | None:
    rows = _query(
        """
        SELECT MAX(timestamp) AS ts FROM (
            SELECT MAX(timestamp) AS timestamp FROM visual_trends WHERE region = ?
            UNION ALL
            SELECT MAX(timestamp) FROM video_hooks WHERE region = ?
            UNION ALL
            SELECT MAX(timestamp) FROM domain_metrics WHERE region = ?
        )
        """,
        (region, region, region),
    )
    if not rows:
        return None
    return parse_timestamp(rows[0].get("ts"))


def latest_rank(region: str, domain: str, keyword: str) -> int | None:
    rows = _query(
        """
        SELECT rank_position FROM domain_metrics
        WHERE region = ? AND domain_name = ? AND target_keyword = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT 1
        """,
        (region, domain, keyword),
    )
    if not rows or rows[0].get("rank_position") is None:
        return None
    return int(rows[0]["rank_position"])


def recent_proposals(region: str, timeframe: str, limit: int = 5) -> list[dict]:
    return _query(
        """
        SELECT * FROM copilot_history
        WHERE region = ? AND timestamp >= ?
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
        """,
        (region, timeframe_cutoff(timeframe), limit),
    )


def _write(conn: sqlite3.Connection | None, sql: str, params: tuple) -> None:
    if conn is not None:
        conn.execute(sql, params)
        return
    with connect() as owned:
        owned.execute(sql, params)


def insert_visual(item: dict, conn: sqlite3.Connection | None = None) -> None:
    _write(
        conn,
        """
        INSERT INTO visual_trends (
            region, hex_codes, ad_format, active_days, screenshot_url,
            timestamp, insight, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["region"],
            json.dumps(item["hex_codes"], ensure_ascii=False),
            item["ad_format"],
            int(item["active_days"]),
            item.get("screenshot_url") or "",
            item.get("timestamp") or utc_now(),
            item.get("insight") or "",
            item.get("source") or "STUDIO BASELINE",
        ),
    )


def insert_hook(item: dict, conn: sqlite3.Connection | None = None) -> None:
    structure = item.get("script_structure") or {}
    if not isinstance(structure, str):
        structure = json.dumps(structure, ensure_ascii=False)
    _write(
        conn,
        """
        INSERT INTO video_hooks (
            region, hook_text, archetype, script_structure, engagement_tier,
            timestamp, insight, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["region"],
            item["hook_text"],
            item["archetype"],
            structure,
            item["engagement_tier"],
            item.get("timestamp") or utc_now(),
            item.get("insight") or "",
            item.get("source") or "STUDIO BASELINE",
        ),
    )


def insert_domain(item: dict, conn: sqlite3.Connection | None = None) -> None:
    change = item.get("rank_change")
    _write(
        conn,
        """
        INSERT INTO domain_metrics (
            region, domain_name, target_keyword, rank_position, rank_change,
            timestamp, insight, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["region"],
            item["domain_name"],
            item["target_keyword"],
            int(item["rank_position"]),
            None if change is None else int(change),
            item.get("timestamp") or utc_now(),
            item.get("insight") or "",
            item.get("source") or "STUDIO BASELINE",
        ),
    )


def insert_proposal(region: str, brief: str, proposal: str, conn: sqlite3.Connection | None = None) -> None:
    _write(
        conn,
        """
        INSERT INTO copilot_history (client_brief, region, generated_proposal, timestamp)
        VALUES (?, ?, ?, ?)
        """,
        (brief, region, proposal, utc_now()),
    )


def table_count(table: str) -> int:
    allowed = {"visual_trends", "video_hooks", "domain_metrics", "copilot_history"}
    if table not in allowed:
        raise ValueError(table)
    rows = _query(f"SELECT COUNT(*) AS n FROM {table}", ())
    return int(rows[0]["n"]) if rows else 0
