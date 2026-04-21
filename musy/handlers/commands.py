from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..emojis import icon_id

router = Router(name="commands")

START_TEXT = "Привет! Бот работает в inline-режиме — напиши @бот запрос в любом чате."


def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Запустить",
                switch_inline_query_current_chat="",
                icon_custom_emoji_id=icon_id("⚡"),
            ),
            InlineKeyboardButton(
                text="Чарт",
                callback_data="chart:page:1",
                icon_custom_emoji_id=icon_id("🔥"),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Избранное",
                switch_inline_query_current_chat="/favs",
                icon_custom_emoji_id=icon_id("❤️"),
            ),
        ],
    ])


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "друг"
    await message.reply(
        f"Привет, {name}! Бот работает в inline-режиме — напиши @бот запрос в любом чате.",
        reply_markup=start_kb(),
    )
