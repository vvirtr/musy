from __future__ import annotations

from typing import Any

_MEDALS = {1: "①", 2: "②", 3: "③"}


def _cdn(uri: str | None, size: str) -> str | None:
    if not uri:
        return None
    return f"https://{uri.replace('%%', size)}"


def _fmt_count(n: int) -> str:
    for unit, step in (("M", 1_000_000), ("K", 1_000)):
        if n >= step:
            return f"{n / step:.1f}".rstrip("0").rstrip(".") + unit
    return str(n)


def artists_str(track: Any) -> str:
    return ", ".join(a.name for a in track.artists) if track.artists else ""


def track_title(track: Any) -> str:
    """Title with a ``version`` suffix if Yandex provides one (Slowed, Sped Up…)."""
    version = getattr(track, "version", None)
    return f"{track.title} {version}" if version else track.title


def rank(i: int) -> str:
    return _MEDALS.get(i, str(i))


def cover_url(track: Any, size: str = "200x200") -> str | None:
    return _cdn(getattr(track, "cover_uri", None), size)


def artist_cover_url(artist: Any, size: str = "200x200") -> str | None:
    uri = getattr(artist, "og_image", None)
    if not uri:
        cover = getattr(artist, "cover", None)
        uri = getattr(cover, "uri", None) if cover is not None else None
    return _cdn(uri, size)


def _listeners_str(artist: Any) -> str | None:
    n = getattr(artist, "listeners_month", None)
    return f"{_fmt_count(n)} слушателей/мес" if n else None


def _rank_str(ratings: Any) -> str | None:
    month = getattr(ratings, "month", 0) if ratings else 0
    if not month or month > 100:
        return None
    return f"#{month} в чарте за месяц"


def _description_text(artist: Any) -> str | None:
    d = getattr(artist, "description", None)
    if not d:
        return None
    return d if isinstance(d, str) else getattr(d, "text", None)


def artist_info_text(artist: Any) -> str:
    lines = [f"◌ {artist.name}"]

    if genres := getattr(artist, "genres", None):
        lines.append("Жанры: " + ", ".join(genres))
    if countries := getattr(artist, "countries", None):
        lines.append("Страна: " + ", ".join(countries))

    counts = getattr(artist, "counts", None)
    if counts:
        parts: list[str] = []
        if getattr(counts, "tracks", 0):
            parts.append(f"треков: {counts.tracks}")
        if getattr(counts, "direct_albums", 0):
            parts.append(f"альбомов: {counts.direct_albums}")
        if parts:
            lines.append(" · ".join(parts))

    listeners = getattr(artist, "listeners_month", None)
    if listeners:
        lines.append(f"Слушателей за месяц: {_fmt_count(listeners)}")
    if rank_line := _rank_str(getattr(artist, "ratings", None)):
        lines.append(rank_line)
    if description := _description_text(artist):
        lines.append("")
        lines.append(description)
    return "\n".join(lines)


def artist_summary(artist: Any) -> str:
    bits: list[str] = []
    if genres := getattr(artist, "genres", None):
        bits.append(", ".join(genres[:2]))

    if listeners := _listeners_str(artist):
        bits.append(listeners)
    elif rank_line := _rank_str(getattr(artist, "ratings", None)):
        bits.append(rank_line)
    else:
        counts = getattr(artist, "counts", None)
        tracks = getattr(counts, "tracks", 0) if counts else 0
        if tracks:
            bits.append(f"{tracks} треков")
    return " · ".join(bits)


def track_info_text(track: Any) -> str:
    lines = [f"{track_title(track)} — {artists_str(track)}"]
    album = track.albums[0] if getattr(track, "albums", None) else None
    if album:
        if album.title:
            lines.append(f"Альбом: {album.title}")
        if album.genre:
            lines.append(f"Жанр: {album.genre}")
        if album.year:
            lines.append(f"Год выпуска: {album.year}")
    return "\n".join(lines)
