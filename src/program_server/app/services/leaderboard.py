from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator


class Leaderboard:
    """Persistent team leaderboard backed by a small SQLite file.

    Scores accumulate across games (one row per finished game) so several
    teams can play during a demo and be ranked against each other. The file
    can be wiped with :meth:`clear` to start a fresh demo.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite connections are not shareable across threads; the game loop and
        # the request handlers may both touch the DB, so guard every access with
        # a lock and open a short-lived connection per call (writes are tiny).
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._path)
        con.row_factory = sqlite3.Row
        return con

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as con:
            with con:
                yield con

    def _init_db(self) -> None:
        with self._lock, self._connection() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS scores (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_name    TEXT    NOT NULL,
                    score        REAL    NOT NULL,
                    title        TEXT    NOT NULL DEFAULT '',
                    theme        TEXT    NOT NULL DEFAULT '',
                    round_scores TEXT    NOT NULL DEFAULT '',
                    created_at   REAL    NOT NULL
                )
                """
            )
            # Migration: total_time tracks how fast the matches were cleared
            # (sum of clear times); used to break score ties (faster = better).
            cols = {r["name"] for r in con.execute("PRAGMA table_info(scores)")}
            if "total_time" not in cols:
                con.execute(
                    "ALTER TABLE scores ADD COLUMN total_time REAL NOT NULL DEFAULT 0"
                )

    def add(
        self,
        team_name: str,
        score: float,
        title: str = "",
        theme: str = "",
        round_scores: list[float] | None = None,
        total_time: float = 0.0,
    ) -> int:
        team_name = (team_name or "").strip() or "이름 없는 팀"
        rounds_text = ",".join(str(round(s, 1)) for s in (round_scores or []))
        created_at = time.time()
        with self._lock, self._connection() as con:
            cur = con.execute(
                """
                INSERT INTO scores
                    (team_name, score, title, theme, round_scores, total_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (team_name, float(score), title, theme, rounds_text, float(total_time), created_at),
            )
            return int(cur.lastrowid)

    def top(self, limit: int = 50) -> list[dict[str, object]]:
        with self._lock, self._connection() as con:
            rows = con.execute(
                """
                SELECT id, team_name, score, title, theme, round_scores, total_time, created_at
                FROM scores
                ORDER BY score DESC, total_time ASC, created_at ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        results: list[dict[str, object]] = []
        for rank, row in enumerate(rows, start=1):
            results.append(
                {
                    "rank": rank,
                    "id": row["id"],
                    "team_name": row["team_name"],
                    "score": round(row["score"], 1),
                    "title": row["title"],
                    "theme": row["theme"],
                    "total_time": round(row["total_time"], 1),
                    "created_at": row["created_at"],
                }
            )
        return results

    def count(self) -> int:
        with self._lock, self._connection() as con:
            row = con.execute("SELECT COUNT(*) AS n FROM scores").fetchone()
            return int(row["n"]) if row else 0

    def clear(self) -> int:
        """Delete every entry and reset the auto-increment counter. Returns the
        number of rows that were removed."""
        with self._lock, self._connection() as con:
            removed = con.execute("SELECT COUNT(*) AS n FROM scores").fetchone()["n"]
            con.execute("DELETE FROM scores")
            # Reset AUTOINCREMENT so the next demo starts at id 1 again.
            con.execute("DELETE FROM sqlite_sequence WHERE name = 'scores'")
            return int(removed)
