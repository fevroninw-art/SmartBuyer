# sources.py

from typing import List, Dict
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


def fetch_avito(query: str) -> List[Dict]:
    q = quote_plus(query)
    url = f"https://www.avito.ru/all?q={q}"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        r = httpx.get(url, headers=headers, timeout=15.0)
        r.raise_for_status()
        size = len(r.text)

        return [{
            "title": f"[avito] страница получена ({size} bytes)",
            "price": 10**18,
            "url": url,
            "source": "avito",
        }]

    except Exception as e:
        return [{
            "title": f"[avito] ошибка: {type(e).__name__}",
            "price": 10**18,
            "url": url,
            "source": "avito",
        }]


def fetch_offers(query: str) -> List[Dict]:
    offers: List[Dict] = []

    offers.extend(fetch_stub(query))
    offers.extend(fetch_avito(query))

    return offers
