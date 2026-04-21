from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_token: str
    yandex_music_token: str
    yandex_music_proxy: str | None = None
    chart_id: str = "russia"
    page_size: int = 20
    search_limit: int = 20
    inline_cache_time: int = 300
    db_path: str = "musy.db"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        tg = os.getenv("TELEGRAM_API_KEY")
        ya = os.getenv("YA_MUSIC_API_KEY")
        missing = [k for k, v in (("TELEGRAM_API_KEY", tg), ("YA_MUSIC_API_KEY", ya)) if not v]
        if missing:
            raise RuntimeError(f"missing env vars: {', '.join(missing)}")
        return cls(
            telegram_token=tg,
            yandex_music_token=ya,
            yandex_music_proxy=os.getenv("YA_MUSIC_PROXY") or None,
            chart_id=os.getenv("YA_CHART_ID", "russia"),
            db_path=os.getenv("MUSY_DB_PATH", "musy.db"),
        )
