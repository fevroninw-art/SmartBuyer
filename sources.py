# sources.py
from __future__ import annotations

from typing import List, Dict, Optional
import httpx


WB_SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v5/search"


def _fetch_wb(query: str, limit: int = 10) -> List[Dict]:
    """
    Достаём товары из Wildberries через публичный endpoint поиска.
    Важно: это не официальная документация, endpoint может меняться.
    """
    params = {
        "query": query,
        "resultset": "catalog",
        "sort": "popular",
        "page": 1,
        "limit": limit,
        "dest": -1257786,  # Москва (типовой dest; можно не трогать)
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SmartBuyerBot/1.0)",
        "Accept": "application/json",
    }

    with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
        r = client.get(WB_SEARCH_URL, params=params)
        r.raise_for_status()
        data = r.json()

    products = (((data or {}).get("data") or {}).get("products")) or []
    offers: List[Dict] = []

    for p in products[:limit]:
        pid = p.get("id") or p.get("nmId")
        title = p.get("name") or "WB товар"

        # priceU обычно в копейках/центах (условная “минимальная цена”)
        price_u = p.get("priceU")
        price: Optional[int] = None
        if isinstance(price_u, int):
            price = price_u // 100  # приводим к рублям

        url = f"https://www.wildberries.ru/catalog/{pid}/detail.aspx" if pid else "https://www.wildberries.ru/"

        offers.append(
            {
                "title": title,
                "price": price,  # может быть None
                "url": url,
                "source": "wb",
            }
        )

    return offers


def _fetch_stub(query: str) -> List[Dict]:
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1", "source": "stub"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2", "source": "stub"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3", "source": "stub"},
    ]


def fetch_offers(query: str, limit: int = 10) -> List[Dict]:
    """
    Единая точка получения офферов.
    Сейчас: stub + wildberries.
    """
    offers: List[Dict] = []
    offers.extend(_fetch_stub(query))

    try:
        offers.extend(_fetch_wb(query, limit=limit))
    except Exception as e:
        # чтобы бот не падал — показываем “мягкую” ошибку в выдаче
        offers.append(
            {
                "title": f"[wb] ошибка: {type(e).__name__}",
                "price": None,
                "url": "",
                "source": "wb",
            }
        )

    return offers
