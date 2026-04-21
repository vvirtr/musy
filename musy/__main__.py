from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from .config import Settings
from .db import Db
from .handlers import chart, commands, favorites, inline
from .music import YaMusic

log = logging.getLogger("musy")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings.from_env()

    log.info("opening db at %s", settings.db_path)
    db = await Db.connect(settings.db_path)

    log.info("connecting to Yandex Music…")
    music = await YaMusic.connect(
        settings.yandex_music_token,
        proxy_url=settings.yandex_music_proxy,
        chart_id=settings.chart_id,
    )

    bot = Bot(settings.telegram_token)
    dp = Dispatcher()
    dp.include_router(commands.router)
    dp.include_router(chart.router)
    dp.include_router(favorites.router)
    dp.include_router(inline.router)

    log.info("starting polling")
    try:
        await dp.start_polling(
            bot,
            music=music,
            db=db,
            page_size=settings.page_size,
            search_limit=settings.search_limit,
        )
    finally:
        await asyncio.gather(
            music.close(),
            db.close(),
            bot.session.close(),
            return_exceptions=True,
        )


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
