# sources.py
from __future__ import annotations

from typing import List, Dict, Optional
from urllib.parse import quote_plus

import httpx


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)


def fetch_stub(query: str) -> List[Dict]:
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1", "source": "stub"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2", "source": "stub"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3", "source": "stub"},
    ]


async def _fetch_avito_html(query: str, timeout_s: float = 15.0) -> str:
    # Простой поиск по Avito (HTML). Без парсинга пока — шаг 1: убедиться, что запрос/ответ работает.
    q = quote_plus(query)
    url = f"https://www.avito.ru/all?q={q}"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    async with httpx.AsyncClient(headers=headers, timeout=timeout_s, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


def fetch_avito(query: str, max_items: int = 10) -> List[Dict]:
    """
    Шаг 1: НЕ парсим предложения, только проверяем что Avito отдаёт страницу.
    Возвращаем один "технический" оффер, чтобы увидеть в Телеграме, что источник работает.
    """
    try:
        html = asyncio_run(_fetch_avito_html(query))
        # маленький маркер, что html действительно пришёл
        size = len(html)
        return [{
            "title": f"[avito] страница получена ({size} bytes)",
            "price": 10**18,
            "url": f"https://www.avito.ru/all?q={quote_plus(query)}",
            "source": "avito",
        }]
    except Exception as e:
        return [{
            "title": f"[avito] ошибка: {type(e).__name__}",
            "price": 10**18,
            "url": f"https://www.avito.ru/all?q={quote_plus(query)}",
            "source": "avito",
        }]


def fetch_offers(query: str, max_items: int = 10) -> List[Dict]:
    """
    Единая точка: собираем офферы из источников.
    Пока: stub + проверка доступности Avito (без парсинга).
    """
    offers: List[Dict] = []
    offers.extend(fetch_stub(query))
    offers.extend(fetch_avito(query, max_items=max_items))
    return offers[:max_items]


# --- маленький хелпер для запуска async из sync ---
def asyncio_run(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    # если мы уже внутри event loop (на Render/uvicorn такое возможно),
    # делаем новый loop в отдельном потоке — но это уже усложнение.
    # Для простоты: если loop есть — просто кидаем исключение с понятным текстом.
    if loop and loop.is_running():
        raise RuntimeError("asyncio_run called inside running event loop")

    return asyncio.run(coro)
