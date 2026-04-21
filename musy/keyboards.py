from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def fav_label(is_fav: bool) -> str:
    return "● Убрать" if is_fav else "○ Добавить"


def track_kb(track_id: str) -> InlineKeyboardMarkup:
    """Article-result keyboard: a single Download button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="↓ Скачать",
            switch_inline_query_current_chat=f"/dbi {track_id}",
        ),
    ]])


def audio_kb(track_id: str, is_fav: bool) -> InlineKeyboardMarkup:
    """Audio-message keyboard: favourite toggle + Info."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=fav_label(is_fav), callback_data=f"fav:{track_id}"),
        InlineKeyboardButton(text="ⓘ Инфо", switch_inline_query_current_chat=f"/info {track_id}"),
    ]])
