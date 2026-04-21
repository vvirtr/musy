from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS favorites (
    user_id    INTEGER NOT NULL,
    track_id   TEXT    NOT NULL,
    added_at   INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (user_id, track_id)
);
CREATE INDEX IF NOT EXISTS favorites_by_user
    ON favorites(user_id, added_at DESC);
"""


class Db:
    """Thin aiosqlite wrapper with a single persistent connection."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def connect(cls, path: str | Path) -> "Db":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(path)
        await conn.executescript(_SCHEMA)
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()

    async def is_favorite(self, user_id: int, track_id: str) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND track_id=? LIMIT 1",
            (user_id, str(track_id)),
        ) as cur:
            return await cur.fetchone() is not None

    async def toggle_favorite(self, user_id: int, track_id: str) -> bool:
        """Toggle; returns new state (True = now a favorite)."""
        tid = str(track_id)
        if await self.is_favorite(user_id, tid):
            await self._conn.execute(
                "DELETE FROM favorites WHERE user_id=? AND track_id=?",
                (user_id, tid),
            )
            await self._conn.commit()
            return False
        await self._conn.execute(
            "INSERT OR IGNORE INTO favorites(user_id, track_id) VALUES (?, ?)",
            (user_id, tid),
        )
        await self._conn.commit()
        return True

    async def favorites(self, user_id: int, limit: int = 50) -> list[str]:
        async with self._conn.execute(
            "SELECT track_id FROM favorites WHERE user_id=? "
            "ORDER BY added_at DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return [row[0] for row in await cur.fetchall()]

    async def favorites_set(self, user_id: int) -> set[str]:
        async with self._conn.execute(
            "SELECT track_id FROM favorites WHERE user_id=?", (user_id,),
        ) as cur:
            return {row[0] for row in await cur.fetchall()}
