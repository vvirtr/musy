from __future__ import annotations

import logging
import math

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from ..emojis import icon_id, render_html
from ..formatting import artists_str, rank
from ..music import YaMusic
from .commands import START_TEXT, start_kb

log = logging.getLogger(__name__)
router = Router(name="chart")

CHART_TEXT = render_html("Треки, популярные на Яндекс Музыке прямо сейчас 🔥")


def _build_keyboard(tracks, page: int, page_size: int) -> InlineKeyboardMarkup:
    total = max(1, math.ceil(len(tracks) / page_size))
    page = max(1, min(page, total))
    start = (page - 1) * page_size

    rows: list[list[InlineKeyboardButton]] = [[
        InlineKeyboardButton(
            text="Чарт Яндекс Музыки",
            callback_data="chart:noop",
            icon_custom_emoji_id=icon_id("🔥"),
        ),
    ]]
    for i, entry in enumerate(tracks[start:start + page_size], start=start + 1):
        t = entry.track
        rows.append([InlineKeyboardButton(
            text=f"{rank(i)}. {t.title} — {artists_str(t)}",
            switch_inline_query_current_chat=f"/dbi {t.id}",
        )])

    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="‹", callback_data=f"chart:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total}", callback_data="chart:noop"))
    if page < total:
        nav.append(InlineKeyboardButton(text="›", callback_data=f"chart:page:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="← Назад", callback_data="chart:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _safe_edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup,
                     *, parse_mode: str | None = None) -> None:
    if not cb.message:
        return
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            log.warning("edit failed: %s", e)


@router.callback_query(F.data.startswith("chart:page:"))
async def chart_page(cb: CallbackQuery, music: YaMusic, page_size: int) -> None:
    page = int(cb.data.rsplit(":", 1)[1])
    try:
        tracks = await music.get_chart()
    except Exception:
        log.exception("chart fetch failed")
        await cb.answer("Яндекс Музыка сейчас недоступна", show_alert=True)
        return
    if not tracks:
        await cb.answer("Чарт пуст", show_alert=True)
        return
    await _safe_edit(cb, CHART_TEXT, _build_keyboard(tracks, page, page_size), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "chart:back")
async def chart_back(cb: CallbackQuery) -> None:
    await _safe_edit(cb, START_TEXT, start_kb())
    await cb.answer()


@router.callback_query(F.data == "chart:noop")
async def chart_noop(cb: CallbackQuery) -> None:
    await cb.answer()
