from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp_socks import ProxyConnector
from yandex_music import Album, Artist, ClientAsync, Track
from yandex_music.exceptions import NetworkError, TimedOutError
from yandex_music.utils.request_async import Request

from .cache import AsyncTTLCache

log = logging.getLogger(__name__)

_SOCKS_SCHEMES = ("socks4://", "socks5://", "socks5h://")
_DOWNLOAD_CONCURRENCY = 3


class _SocksRequest(Request):
    """Request that supports SOCKS/HTTP proxies via a shared aiohttp session.

    The upstream ``Request`` forwards ``proxy_url`` to aiohttp's ``proxy=`` kwarg,
    which only understands http/https schemes. For SOCKS we hand off to
    ``aiohttp-socks``' ``ProxyConnector`` and reuse one session across requests.
    """

    def __init__(self, proxy_url: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._proxy_url = proxy_url
        self.proxy_url = None  # prevent the base class from handing it to aiohttp
        self._session: aiohttp.ClientSession | None = None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request_wrapper(self, *args: Any, **kwargs: Any) -> bytes:
        kwargs = self._prepare_kwargs(kwargs)
        kwargs.pop("proxy", None)
        session = await self._ensure_session()
        try:
            async with session.request(*args, **kwargs) as resp:
                content = await resp.content.read()
        except asyncio.TimeoutError as e:
            raise TimedOutError from e
        except aiohttp.ClientError as e:
            raise NetworkError(e) from e

        if 200 <= resp.status <= 299:
            return content
        self._handle_error_response(resp.status, content)
        return None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=ProxyConnector.from_url(self._proxy_url),
            )
        return self._session


def _build_request(proxy_url: str | None) -> Request | None:
    if not proxy_url:
        return None
    if proxy_url.startswith(_SOCKS_SCHEMES):
        return _SocksRequest(proxy_url=proxy_url)
    return Request(proxy_url=proxy_url)


class YaMusic:
    """Async facade over ``yandex_music.ClientAsync`` with per-entity caches."""

    def __init__(
        self,
        client: ClientAsync,
        *,
        request: Request | None = None,
        chart_id: str = "russia",
    ) -> None:
        self._client = client
        self._request = request
        self._chart_id = chart_id

        # per-entity caches — TTLs picked from how fast the upstream data moves.
        self._search_cache: AsyncTTLCache[list[Track]] = AsyncTTLCache(ttl=300, max_size=2048)
        self._track_cache: AsyncTTLCache[Track | None] = AsyncTTLCache(ttl=1800, max_size=2048)
        self._lyrics_cache: AsyncTTLCache[str | None] = AsyncTTLCache(ttl=1800, max_size=1024)
        self._url_cache: AsyncTTLCache[str] = AsyncTTLCache(ttl=600, max_size=2048)
        self._album_cache: AsyncTTLCache[Album | None] = AsyncTTLCache(ttl=1800, max_size=512)
        self._artist_cache: AsyncTTLCache[Artist | None] = AsyncTTLCache(ttl=1800, max_size=512)
        self._artist_top_cache: AsyncTTLCache[list[Track]] = AsyncTTLCache(ttl=1800, max_size=512)
        self._similar_cache: AsyncTTLCache[list[Track]] = AsyncTTLCache(ttl=1800, max_size=1024)
        self._chart_cache: AsyncTTLCache[list[Any]] = AsyncTTLCache(ttl=120, max_size=4)

        self._download_sem = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)

    @classmethod
    async def connect(
        cls,
        token: str,
        *,
        proxy_url: str | None = None,
        chart_id: str = "russia",
    ) -> "YaMusic":
        request = _build_request(proxy_url)
        client = await ClientAsync(token, request=request).init()
        return cls(client, request=request, chart_id=chart_id)

    async def close(self) -> None:
        if isinstance(self._request, _SocksRequest):
            await self._request.close()

    async def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        key = ("search", query.strip().lower(), limit)

        async def fetch() -> list[Track]:
            result = await self._client.search(query, type_="track")
            if not result or not result.tracks or not result.tracks.results:
                return []
            return result.tracks.results[:limit]

        return await self._search_cache.get_or_set(key, fetch)

    async def get_track(self, track_id: str) -> Track | None:
        async def fetch() -> Track | None:
            tracks = await self._client.tracks(track_id)
            return tracks[0] if tracks else None

        return await self._track_cache.get_or_set(str(track_id), fetch)

    async def get_tracks(self, track_ids: list[str]) -> list[Track]:
        """Batch-fetch, preserving order; missing ids are skipped."""
        if not track_ids:
            return []

        missing = [tid for tid in track_ids if self._track_cache.peek(tid) is None]
        if missing:
            fetched = await self._client.tracks(missing) or []
            for t in fetched:
                self._track_cache.set(str(t.id), t)

        return [t for tid in track_ids if (t := self._track_cache.peek(tid)) is not None]

    async def get_lyrics(self, track_id: str) -> str | None:
        async def fetch() -> str | None:
            try:
                lyr = await self._client.tracks_lyrics(track_id, "TEXT")
            except Exception:
                log.debug("no lyrics for %s", track_id, exc_info=True)
                return None
            return await lyr.fetch_lyrics_async() if lyr else None

        return await self._lyrics_cache.get_or_set(str(track_id), fetch)

    async def get_album(self, album_id: str) -> Album | None:
        async def fetch() -> Album | None:
            return await self._client.albums_with_tracks(album_id)

        return await self._album_cache.get_or_set(str(album_id), fetch)

    async def get_artist(self, artist_id: str) -> Artist | None:
        """Rich ``Artist`` from brief_info (listeners count, bio, etc.)."""

        async def fetch() -> Artist | None:
            bi = await self._client.artists_brief_info(artist_id)
            if not bi or not bi.artist:
                return None
            artist = bi.artist
            if (stats := getattr(bi, "stats", None)) is not None:
                artist.listeners_month = getattr(stats, "last_month_listeners", None)
                artist.listeners_delta = getattr(stats, "last_month_listeners_delta", None)
            return artist

        return await self._artist_cache.get_or_set(str(artist_id), fetch)

    async def get_artist_top_tracks(self, artist_id: str, limit: int = 20) -> list[Track]:
        async def fetch() -> list[Track]:
            result = await self._client.artists_tracks(artist_id, page=0, page_size=limit)
            return list(result.tracks) if result and result.tracks else []

        return await self._artist_top_cache.get_or_set(f"{artist_id}:{limit}", fetch)

    async def get_similar_tracks(self, track_id: str, limit: int = 20) -> list[Track]:
        async def fetch() -> list[Track]:
            sim = await self._client.tracks_similar(track_id)
            return list(sim.similar_tracks)[:limit] if sim and sim.similar_tracks else []

        return await self._similar_cache.get_or_set(f"{track_id}:{limit}", fetch)

    async def get_chart(self) -> list[Any]:
        async def fetch() -> list[Any]:
            chart = await self._client.chart(self._chart_id)
            return chart.chart.tracks if chart and chart.chart else []

        return await self._chart_cache.get_or_set(self._chart_id, fetch)

    async def get_download_url(self, track: Track) -> str:
        async def fetch() -> str:
            async with self._download_sem:
                infos = await track.get_download_info_async()
                mp3 = [i for i in infos if i.codec == "mp3"] or infos
                best = max(mp3, key=lambda i: int(i.bitrate_in_kbps))
                return await best.get_direct_link_async()

        return await self._url_cache.get_or_set(str(track.id), fetch)

    async def resolve_urls(self, tracks: list[Track]) -> dict[str, str]:
        """Parallel-resolve download URLs; failures are silently skipped."""

        async def resolve(t: Track) -> tuple[str, str | None]:
            try:
                return str(t.id), await self.get_download_url(t)
            except Exception:
                log.debug("url resolve failed for %s", t.id, exc_info=True)
                return str(t.id), None

        pairs = await asyncio.gather(*(resolve(t) for t in tracks))
        return {tid: url for tid, url in pairs if url}
