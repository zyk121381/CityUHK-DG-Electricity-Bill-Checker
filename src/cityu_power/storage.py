"""
SQLite 存储。
readings 存读数快照，notices 存通知幂等标记。
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    day         TEXT NOT NULL,
    room        TEXT,
    balance_kwh REAL,
    balance_cny REAL,
    source      TEXT,
    meta        TEXT
);
CREATE INDEX IF NOT EXISTS idx_readings_ts  ON readings(ts);
CREATE INDEX IF NOT EXISTS idx_readings_day ON readings(day);

CREATE TABLE IF NOT EXISTS notices (
    key TEXT PRIMARY KEY,
    ts  TEXT NOT NULL
);
"""

_SELECT = (
    "SELECT ts, day, room, balance_kwh, balance_cny, source, meta FROM readings"
)


class Storage:
    """读数与通知记录的读写。"""
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def add(self, reading: Reading) -> int:
        cur = self.conn.execute(
            "INSERT INTO readings (ts, day, room, balance_kwh, balance_cny, source, meta)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            reading.to_row(),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def latest(self) -> Reading | None:
        row = self.conn.execute(
            _SELECT + " ORDER BY ts DESC, id DESC LIMIT 1"
        ).fetchone()
        return Reading.from_row(row) if row else None

    def last(self, limit: int = 20) -> list[Reading]:
        rows = self.conn.execute(
            _SELECT + " ORDER BY ts DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Reading.from_row(r) for r in rows]

    def daily_latest(self, days: int = 14) -> list[Reading]:
        """每天取最后一条读数，按时间升序返回。"""
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """
            SELECT ts, day, room, balance_kwh, balance_cny, source, meta
            FROM readings r
            WHERE day >= ?
              AND id = (
                  SELECT id FROM readings
                  WHERE day = r.day ORDER BY ts DESC, id DESC LIMIT 1
              )
            ORDER BY day ASC
            """,
            (since,),
        ).fetchall()
        return [Reading.from_row(r) for r in rows]

    def day_count(self) -> int:
        (n,) = self.conn.execute("SELECT COUNT(DISTINCT day) FROM readings").fetchone()
        return int(n or 0)

    def has_notice(self, key: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM notices WHERE key = ?", (key,)).fetchone()
        return row is not None

    def mark_notice(self, key: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO notices (key, ts) VALUES (?, ?)",
            (key, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def purge_old(self, keep_days: int = 400) -> int:
        cutoff_day = (date.today() - timedelta(days=keep_days)).isoformat()
        cutoff_ts = (
            datetime.now() - timedelta(days=keep_days)
        ).isoformat(timespec="seconds")
        cur = self.conn.execute("DELETE FROM readings WHERE day < ?", (cutoff_day,))
        self.conn.execute("DELETE FROM notices WHERE ts < ?", (cutoff_ts,))
        self.conn.commit()
        return cur.rowcount

    def delete_source(self, source: str) -> int:
        """删掉某个数据源的全部记录，用于清理演示/测试数据。"""
        cur = self.conn.execute("DELETE FROM readings WHERE source = ?", (source,))
        self.conn.commit()
        return cur.rowcount

    def sources(self) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            "SELECT source, COUNT(*) FROM readings GROUP BY source ORDER BY COUNT(*) DESC"
        ).fetchall()
        return [(r[0] or "", int(r[1])) for r in rows]

    def close(self) -> None:
        self.conn.close()
