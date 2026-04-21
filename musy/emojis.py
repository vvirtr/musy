from __future__ import annotations

import html as _html

# Vector Icons pack: https://t.me/addemoji/vector_icons_by_fStikBot
# Curated subset used across the bot.
CUSTOM: dict[str, str] = {
    "⚡": "5219943216781995020",
    "🔍": "5258274739041883702",
    "🔥": "5222148368955877900",
    "✍️": "5220046725493828505",
    "🎶": "5222472119295684375",
    "📎": "5454419255430767770",
    "❤️": "5454249887690415056",
    "🎥": "5258217809250372293",
}


def icon_id(emoji: str) -> str | None:
    """Return custom_emoji_id for a button icon, or None if no custom version."""
    return CUSTOM.get(emoji)


def render_html(text: str) -> str:
    """HTML-escape text and wrap known emojis in <tg-emoji>."""
    out = _html.escape(text)
    for emoji, cid in CUSTOM.items():
        out = out.replace(emoji, f'<tg-emoji emoji-id="{cid}">{emoji}</tg-emoji>')
    return out
