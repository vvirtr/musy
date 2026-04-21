from __future__ import annotations

import asyncio
import html
import logging
import uuid

from aiogram import F, Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultAudio,
    InputTextMessageContent,
    LinkPreviewOptions,
)

from ..db import Db
from ..emojis import render_html
from ..formatting import (
    artist_cover_url,
    artist_info_text,
    artist_summary,
    artists_str,
    cover_url,
    track_info_text,
    track_title,
)
from ..keyboards import audio_kb, track_kb
from ..music import YaMusic
from ..yalink import parse as parse_yalink

log = logging.getLogger(__name__)
router = Router(name="inline")

MIN_QUERY_LEN = 3
ALBUM_TRACKS_LIMIT = 50
ARTIST_LIST_LIMIT = 20
FAVS_LIMIT = 20


# --- helpers ----------------------------------------------------------------


def _new_id() -> str:
    return str(uuid.uuid4())


def _arg(query: str, prefix: str) -> str | None:
    rest = query.removeprefix(prefix).strip()
    return rest.split()[0] if rest else None


async def _require_arg(q: InlineQuery, prefix: str) -> str | None:
    """Parse the first arg after ``prefix``; answer with an empty list if missing."""
    arg = _arg(q.query, prefix)
    if arg is None:
        await q.answer([], cache_time=1, is_personal=True)
    return arg


async def _reply_article(
    q: InlineQuery,
    *,
    title: str,
    text: str,
    description: str = "",
    cache_time: int = 10,
) -> None:
    await q.answer(
        [InlineQueryResultArticle(
            id=_new_id(),
            title=title,
            description=description,
            input_message_content=InputTextMessageContent(message_text=text),
        )],
        cache_time=cache_time,
        is_personal=True,
    )


def _html_with_preview(body_html: str, media_url: str | None
                       ) -> tuple[str, LinkPreviewOptions | None]:
    """Attach a hidden link to ``media_url`` so Telegram renders it as a large preview."""
    if not media_url:
        return body_html, None
    anchor = f'<a href="{html.escape(media_url, quote=True)}">\u200b</a>'
    preview = LinkPreviewOptions(url=media_url, prefer_large_media=True, show_above_text=True)
    return f"{anchor}{body_html}", preview


# --- result factories -------------------------------------------------------


def _track_result(track) -> InlineQueryResultArticle:
    track_id = str(track.id)
    title = track_title(track)
    performer = artists_str(track)
    message_text, link_preview = _html_with_preview(
        render_html(f"{title} — {performer}"),
        cover_url(track, "1000x1000"),
    )
    return InlineQueryResultArticle(
        id=track_id,
        title=title,
        description=performer,
        input_message_content=InputTextMessageContent(
            message_text=message_text,
            parse_mode="HTML",
            link_preview_options=link_preview,
        ),
        thumbnail_url=cover_url(track, "200x200"),
        thumbnail_width=200,
        thumbnail_height=200,
        reply_markup=track_kb(track_id),
    )


def _audio_result(track, url: str, *, is_fav: bool) -> InlineQueryResultAudio:
    track_id = str(track.id)
    return InlineQueryResultAudio(
        id=f"audio-{track_id}",
        audio_url=url,
        title=track_title(track),
        performer=artists_str(track),
        duration=(track.duration_ms or 0) // 1000,
        reply_markup=audio_kb(track_id, is_fav),
    )


def _track_list(tracks) -> list[InlineQueryResult]:
    return [_track_result(t) for t in tracks]


def _artist_header(artist) -> InlineQueryResultArticle:
    message_text, link_preview = _html_with_preview(
        render_html(artist_info_text(artist)),
        artist_cover_url(artist, "1000x1000"),
    )
    return InlineQueryResultArticle(
        id=f"artist-{artist.id}",
        title=artist.name,
        description=artist_summary(artist) or "Артист",
        input_message_content=InputTextMessageContent(
            message_text=message_text,
            parse_mode="HTML",
            link_preview_options=link_preview,
        ),
        thumbnail_url=artist_cover_url(artist, "200x200"),
        thumbnail_width=200,
        thumbnail_height=200,
    )


def _info_keyboard(track, has_lyrics: bool) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    if has_lyrics:
        rows.append([InlineKeyboardButton(
            text="≡ Текст песни",
            switch_inline_query_current_chat=f"/text {track.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="∿ Похожее",
        switch_inline_query_current_chat=f"/similar {track.id}",
    )])
    if track.albums:
        rows.append([InlineKeyboardButton(
            text="◎ Альбом",
            switch_inline_query_current_chat=f"/album {track.albums[0].id}",
        )])
    for a in track.artists or []:
        name = a.name if len(a.name) <= 40 else a.name[:39] + "…"
        rows.append([InlineKeyboardButton(
            text=f"◌ {name}",
            switch_inline_query_current_chat=f"/artist {a.id}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# --- handlers ---------------------------------------------------------------


@router.inline_query(F.query == "")
async def on_empty(q: InlineQuery) -> None:
    await _reply_article(
        q,
        title="Введите название трека",
        description="Начните печатать, чтобы найти музыку",
        text="Используйте inline-режим бота для поиска музыки.",
        cache_time=60,
    )


@router.inline_query(F.query.startswith("/start"))
async def on_start(q: InlineQuery) -> None:
    await _reply_article(
        q,
        title="Введите название трека вместо /start",
        description="Начните пользоваться ботом!",
        text="Просто напиши название трека в inline-режиме.",
        cache_time=60,
    )


@router.inline_query(F.query.startswith("/dbi "))
async def on_download(q: InlineQuery, music: YaMusic, db: Db) -> None:
    track_id = await _require_arg(q, "/dbi")
    if not track_id:
        return

    try:
        track = await music.get_track(track_id)
        if not track:
            raise LookupError(track_id)
        url = await music.get_download_url(track)
    except Exception:
        log.exception("download failed: %s", track_id)
        await _reply_article(
            q,
            title="Не удалось получить трек",
            description="Попробуйте ещё раз",
            text="Ошибка при получении трека.",
            cache_time=1,
        )
        return

    is_fav = await db.is_favorite(q.from_user.id, track_id) if q.from_user else False
    await q.answer(
        [InlineQueryResultAudio(
            id=_new_id(),
            audio_url=url,
            title=track_title(track),
            performer=artists_str(track),
            duration=(track.duration_ms or 0) // 1000,
            reply_markup=audio_kb(track_id, is_fav),
        )],
        cache_time=1,
        is_personal=True,
    )


@router.inline_query(F.query.startswith("/info "))
async def on_info(q: InlineQuery, music: YaMusic) -> None:
    track_id = await _require_arg(q, "/info")
    if not track_id:
        return

    track, lyrics = await asyncio.gather(
        music.get_track(track_id),
        music.get_lyrics(track_id),
    )
    if not track:
        await _reply_article(q, title="Трек не найден", text="Трек не найден.")
        return

    message_text, link_preview = _html_with_preview(
        render_html(track_info_text(track)),
        cover_url(track, "1000x1000"),
    )
    await q.answer(
        [InlineQueryResultArticle(
            id=_new_id(),
            title=track_title(track),
            description=artists_str(track),
            input_message_content=InputTextMessageContent(
                message_text=message_text,
                parse_mode="HTML",
                link_preview_options=link_preview,
            ),
            thumbnail_url=cover_url(track, "200x200"),
            thumbnail_width=200,
            thumbnail_height=200,
            reply_markup=_info_keyboard(track, has_lyrics=bool(lyrics)),
        )],
        cache_time=300,
    )


@router.inline_query(F.query.startswith("/text "))
async def on_text(q: InlineQuery, music: YaMusic) -> None:
    track_id = await _require_arg(q, "/text")
    if not track_id:
        return

    track, lyrics = await asyncio.gather(
        music.get_track(track_id),
        music.get_lyrics(track_id),
    )
    if not track:
        await _reply_article(q, title="Трек не найден", text="Трек не найден.")
        return

    text = f"{track_title(track)} — {artists_str(track)}\n\n{lyrics or 'Текст не найден.'}"
    await q.answer(
        [InlineQueryResultArticle(
            id=_new_id(),
            title=track_title(track),
            description="Текст песни",
            input_message_content=InputTextMessageContent(message_text=text),
            thumbnail_url=cover_url(track, "200x200"),
            thumbnail_width=200,
            thumbnail_height=200,
        )],
        cache_time=300,
    )


@router.inline_query(F.query.startswith("/album "))
async def on_album(q: InlineQuery, music: YaMusic) -> None:
    album_id = await _require_arg(q, "/album")
    if not album_id:
        return

    try:
        album = await music.get_album(album_id)
    except Exception:
        log.exception("album fetch failed: %s", album_id)
        album = None

    if not album or not album.volumes:
        await _reply_article(q, title="Альбом не найден", text="Альбом не найден.")
        return

    tracks = [t for volume in album.volumes for t in volume][:ALBUM_TRACKS_LIMIT]
    if not tracks:
        await _reply_article(q, title="В альбоме нет треков", text="Альбом пуст.")
        return
    await q.answer(_track_list(tracks), cache_time=10, is_personal=True)


@router.inline_query(F.query.startswith("/artist "))
async def on_artist(q: InlineQuery, music: YaMusic, search_limit: int) -> None:
    artist_id = await _require_arg(q, "/artist")
    if not artist_id:
        return

    limit = max(search_limit, ARTIST_LIST_LIMIT)
    try:
        artist, tracks = await asyncio.gather(
            music.get_artist(artist_id),
            music.get_artist_top_tracks(artist_id, limit=limit),
        )
    except Exception:
        log.exception("artist fetch failed: %s", artist_id)
        artist, tracks = None, []

    if not artist and not tracks:
        await _reply_article(q, title="Артист не найден", text="Ничего не найдено.")
        return

    results: list[InlineQueryResult] = []
    if artist:
        results.append(_artist_header(artist))
    results.extend(_track_list(tracks))
    await q.answer(results, cache_time=10, is_personal=True)


@router.inline_query(F.query.startswith("/similar "))
async def on_similar(q: InlineQuery, music: YaMusic, search_limit: int) -> None:
    track_id = await _require_arg(q, "/similar")
    if not track_id:
        return

    try:
        tracks = await music.get_similar_tracks(track_id, limit=max(search_limit, ARTIST_LIST_LIMIT))
    except Exception:
        log.exception("similar fetch failed: %s", track_id)
        tracks = []

    if not tracks:
        await _reply_article(
            q,
            title="Похожих треков не нашлось",
            text="Для этого трека нет рекомендаций.",
            cache_time=60,
        )
        return
    await q.answer(_track_list(tracks), cache_time=10, is_personal=True)


@router.inline_query(F.query.startswith("/favs"))
async def on_favs(q: InlineQuery, music: YaMusic, db: Db) -> None:
    if not q.from_user:
        await q.answer([], cache_time=1, is_personal=True)
        return

    ids = await db.favorites(q.from_user.id, limit=FAVS_LIMIT)
    if not ids:
        await _reply_article(
            q,
            title="Пока пусто",
            description="Нажмите ♡ на треке, чтобы сохранить его",
            text="Нет сохранённых треков.",
            cache_time=1,
        )
        return

    try:
        tracks = await music.get_tracks(ids)
        urls = await music.resolve_urls(tracks) if tracks else {}
    except Exception:
        log.exception("favs fetch failed")
        tracks, urls = [], {}

    if not tracks:
        await _reply_article(
            q,
            title="Не удалось загрузить избранное",
            description="Попробуйте позже",
            text="Ошибка загрузки.",
            cache_time=1,
        )
        return

    results: list[InlineQueryResult] = []
    for t in tracks:
        tid = str(t.id)
        if tid in urls:
            results.append(_audio_result(t, urls[tid], is_fav=True))
        else:
            results.append(_track_result(t))
    await q.answer(results, cache_time=1, is_personal=True)


@router.inline_query()
async def on_search(q: InlineQuery, music: YaMusic, search_limit: int) -> None:
    query = q.query.strip()

    if link := parse_yalink(query):
        await _resolve_yalink(q, music, link, search_limit)
        return

    if len(query) < MIN_QUERY_LEN:
        await _reply_article(
            q,
            title=f"Введите минимум {MIN_QUERY_LEN} символа",
            description="Короткий запрос — много шума",
            text="Запрос слишком короткий.",
            cache_time=300,
        )
        return

    try:
        tracks = await music.search_tracks(query, limit=search_limit)
    except Exception:
        log.exception("search failed: %r", query)
        await _reply_article(
            q,
            title="Сервис временно недоступен",
            description="Попробуйте позже",
            text="Не удалось выполнить поиск.",
            cache_time=1,
        )
        return

    if not tracks:
        await _reply_article(
            q,
            title="Ничего не найдено",
            description="Попробуйте другой запрос",
            text="По запросу ничего не найдено.",
        )
        return

    await q.answer(_track_list(tracks), cache_time=10, is_personal=True)


async def _resolve_yalink(q: InlineQuery, music: YaMusic, link, search_limit: int) -> None:
    try:
        if link.kind == "track":
            track = await music.get_track(link.id)
            tracks = [track] if track else []
        elif link.kind == "album":
            album = await music.get_album(link.id)
            tracks = ([t for volume in album.volumes for t in volume][:ALBUM_TRACKS_LIMIT]
                      if album and album.volumes else [])
        else:  # artist
            tracks = await music.get_artist_top_tracks(link.id, limit=search_limit)
    except Exception:
        log.exception("yalink fetch failed: %s", link)
        tracks = []

    if tracks:
        await q.answer(_track_list(tracks), cache_time=10, is_personal=True)
        return

    await _reply_article(
        q,
        title="Не удалось открыть ссылку",
        description="Попробуйте другой запрос",
        text="Ссылка недоступна.",
    )
