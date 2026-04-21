from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["track", "album", "artist"]


@dataclass(frozen=True, slots=True)
class YaLink:
    kind: Kind
    id: str


_URL_RE = re.compile(
    r"""
    (?:https?://)?music\.yandex\.(?:ru|com|by|kz|uz)/
    (?:
        (?:album/\d+/)?track/(?P<track>\d+)
      | album/(?P<album>\d+)
      | artist/(?P<artist>\d+)
    )
    """,
    re.VERBOSE,
)


def parse(text: str) -> YaLink | None:
    m = _URL_RE.search(text)
    if not m:
        return None
    if tid := m.group("track"):
        return YaLink("track", tid)
    if aid := m.group("album"):
        return YaLink("album", aid)
    if art := m.group("artist"):
        return YaLink("artist", art)
    return None
