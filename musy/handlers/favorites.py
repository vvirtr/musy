from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from ..db import Db
from ..keyboards import audio_kb

log = logging.getLogger(__name__)
router = Router(name="favorites")


@router.callback_query(F.data.startswith("fav:"))
async def toggle_favorite(cb: CallbackQuery, db: Db) -> None:
    if not cb.from_user or not cb.data:
        await cb.answer()
        return

    track_id = cb.data.removeprefix("fav:")
    if not track_id:
        await cb.answer()
        return

    is_fav = await db.toggle_favorite(cb.from_user.id, track_id)
    new_kb = audio_kb(track_id, is_fav)
    alert = "Добавлено в избранное" if is_fav else "Убрано из избранного"

    try:
        if cb.message:
            await cb.message.edit_reply_markup(reply_markup=new_kb)
        elif cb.inline_message_id:
            await cb.bot.edit_message_reply_markup(
                inline_message_id=cb.inline_message_id,
                reply_markup=new_kb,
            )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            log.warning("fav keyboard edit failed: %s", e)

    await cb.answer(alert)
