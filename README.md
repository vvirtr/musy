# musy

Telegram inline-бот для поиска и отправки треков из Яндекс Музыки.

Работает **только в inline-режиме** — пиши `@musy_bot <запрос>` в любом чате,
и он покажет выдачу; тап по треку → в чат уходит сразу аудио.

## Возможности

- **Inline-поиск** треков с обложкой в превью сообщения.
- **`/dbi <id>`** — отправка аудио в чат.
- **`/info <id>`** — карточка трека: альбом, жанр, год, биография артиста; отдельные
  кнопки «Текст песни», «Похожее», «Альбом», «Артист».
- **`/text <id>`** — текст песни.
- **`/album <id>`**, **`/artist <id>`** — треклист альбома / топ-треки исполнителя
  с шапкой-инфо и обложкой.
- **`/similar <id>`** — похожие треки.
- **`/favs`** — избранное пользователя сразу аудио-результатами, тап = трек.
- **Кнопка `○ / ●`** у каждого аудио — toggle избранного (хранится в локальной SQLite).
- **Ссылки на Яндекс** (`music.yandex.ru/album/…/track/…`, `/album/…`, `/artist/…`) —
  бот распознаёт их прямо в inline-запросе и разворачивает в соответствующий список.
- **Чарт Яндекс Музыки** — команда `/start` → кнопка «Чарт» → пагинация + «Назад».
- **Варианты треков** (`Slowed`, `Ultra Slowed`, `Sped Up`…) — подставляются в
  название из поля `version`, которое Яндекс не кладёт в title.
- **Кастомные эмодзи** на кнопках сообщений бота (требует Premium у владельца, см. ниже).

## Архитектура

```
musy/
├── __main__.py        # точка входа, бутстрап DI (music, db) в aiogram
├── config.py          # dataclass с настройками из .env
├── cache.py           # AsyncTTLCache: LRU + TTL + single-flight
├── music.py           # фасад над yandex_music.ClientAsync + SOCKS5 через aiohttp-socks
├── db.py              # aiosqlite, таблица favorites
├── formatting.py      # рендер названий / артистов / обложек / инфо
├── emojis.py          # карта обычный → custom_emoji_id + render_html()
├── keyboards.py       # сборщики inline-клавиатур
├── yalink.py          # парсер music.yandex.ru ссылок
└── handlers/
    ├── commands.py    # /start
    ├── chart.py       # чарт, пагинация, «Назад»
    ├── favorites.py   # callback toggle ♡
    └── inline.py      # все inline-сценарии
```

### Кэширование

- `search_tracks`, `get_track`, `get_lyrics`, `get_album`, `get_artist`,
  `get_artist_top_tracks`, `get_similar_tracks`, `get_chart`, `get_download_url` —
  всё обёрнуто в `AsyncTTLCache` со своими TTL (от 2 мин для чарта до 30 мин
  для статичных сущностей).
- `single-flight`: параллельные промахи по одному ключу ждут одного общего producer.

### Геоблок

Яндекс отдаёт **451 Unavailable For Legal Reasons** вне РФ/СНГ. Поэтому клиент
гоняется через SOCKS5 — см. `YA_MUSIC_PROXY` ниже. CDN (`avatars.yandex.net`) —
публичный, обложки Telegram-клиент тянет напрямую.

### Telegram Bot API — ограничения

- **Кастомные эмодзи** (`<tg-emoji>`, `icon_custom_emoji_id`) работают только
  в сообщениях, которые **шлёт сам бот** (`/start` reply, чарт). В сообщениях
  из inline-результатов — не применяются (шлёт «пользователь от имени бота»),
  там используются текстовые ASCII-символы (`↓`, `●/○`, `≡`, `∿`, `◎`, `◌`, `ⓘ`).
- **Inline превью-картинка** у `InlineQueryResultArticle` + `LinkPreviewOptions`
  с невидимым HTML-якорем. Так Telegram показывает большую обложку сверху
  текстового сообщения.

## Установка

Требует Python ≥ 3.11.

```bash
git clone https://github.com/vvirtr/musy
cd musy

python -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# заполнить TELEGRAM_API_KEY и YA_MUSIC_API_KEY
# (опционально) YA_MUSIC_PROXY, YA_CHART_ID, MUSY_DB_PATH

musy        # или: python -m musy
```

## Настройки (.env)

| Переменная          | Обязательно | Описание                                                                 |
| ------------------- | :---------: | ------------------------------------------------------------------------ |
| `TELEGRAM_API_KEY`  |      ✓      | Токен бота от [@BotFather](https://t.me/BotFather).                      |
| `YA_MUSIC_API_KEY`  |      ✓      | OAuth-токен Яндекс Музыки (см. [yandex-music-api docs](https://ym.marshal.dev/token/)). |
| `YA_MUSIC_PROXY`    |             | SOCKS5/HTTP URL, если хост вне РФ/СНГ. `socks5://user:pass@host:port`.   |
| `YA_CHART_ID`       |             | Регион чарта: `russia` (по умолчанию), `world`.                          |
| `MUSY_DB_PATH`      |             | Путь к SQLite (`musy.db` рядом с процессом).                             |

## Получение Telegram-токена

1. В [@BotFather](https://t.me/BotFather) создай бота (`/newbot`).
2. В настройках включи inline-режим: `/setinline → Enable`.
3. Опционально: `/setinlinefeedback → Enabled` (если будешь считать статистику).

## Получение токена Яндекс Музыки

Самый простой способ — Device Flow из самой библиотеки:

```python
from yandex_music import Client
Client().device_auth(on_code=lambda c: print(c.verification_url, c.user_code))
```

Откроет ссылку, куда вводишь код из консоли — получишь `access_token`.

## Зависимости

- [aiogram](https://github.com/aiogram/aiogram) ≥ 3.4 — Telegram Bot API
- [yandex-music](https://github.com/MarshalX/yandex-music-api) ≥ 3.0 — API Яндекс Музыки
- [aiohttp-socks](https://pypi.org/project/aiohttp-socks/) — SOCKS-прокси для aiohttp
- [aiosqlite](https://pypi.org/project/aiosqlite/) — async SQLite для избранного
- [python-dotenv](https://pypi.org/project/python-dotenv/) — загрузка `.env`

## Лицензия

MIT
