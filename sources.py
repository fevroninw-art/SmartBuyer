# sources.py

import json
from typing import List, Dict
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup


def fetch_stub(query: str) -> List[Dict]:
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1", "source": "stub"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2", "source": "stub"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3", "source": "stub"},
    ]


def fetch_avito(query: str, *, max_items: int = 10) -> List[Dict]:
    q = quote_plus(query)
    url = f"https://www.avito.ru/all?q={q}"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        r = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
    except Exception:
        return []

    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    out: List[Dict] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, dict) and data.get("@type") == "ItemList":
            for el in data.get("itemListElement", [])[:max_items]:
                it = el.get("item") if isinstance(el, dict) else None
                if not isinstance(it, dict):
                    continue

                title = it.get("name")
                link = it.get("url")
                offers = it.get("offers") or {}
                price = offers.get("price")

                if not title or not link or price is None:
                    continue

                try:
                    price_int = int(float(price))
                except Exception:
                    continue

                if link.startswith("/"):
                    link = "https://www.avito.ru" + link

                out.append(
                    {
                        "title": str(title).strip(),
                        "price": price_int,
                        "url": str(link).strip(),
                        "source": "avito",
                    }
                )
            break

    return out[:max_items]


def fetch_offers(query: str) -> List[Dict]:
    offers: List[Dict] = []

    offers.extend(fetch_avito(query))

    if not offers:
        offers.extend(fetch_stub(query))

    offers.sort(key=lambda x: int(x.get("price", 10**18)))

    return offers
