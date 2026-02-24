# sources.py
from __future__ import annotations

from typing import Callable, Dict, List, Optional


Offer = Dict[str, object]  # {"title": str, "price": int, "url": str, "source": str, ...}

# --- 1) STUB источник (всегда работает) ---
def fetch_stub(query: str, limit: int = 10) -> List[Offer]:
    q = query.strip()
    return [
        {"title": f"{q} (вариант 1)", "price": 79990, "url": "https://example.com/1", "source": "stub"},
        {"title": f"{q} (вариант 2)", "price": 82990, "url": "https://example.com/2", "source": "stub"},
        {"title": f"{q} (вариант 3)", "price": 85990, "url": "https://example.com/3", "source": "stub"},
    ][:limit]


# --- 2) Реальные источники подключаем позже ---
# Здесь будут fetch_avito(), fetch_ozon(), fetch_wb() и т.д.
# ВАЖНО: пока не делаем сетевые запросы — только каркас.
SourceFunc = Callable[[str, int], List[Offer]]

SOURCES: Dict[str, SourceFunc] = {
    "stub": fetch_stub,
    # "avito": fetch_avito,   # подключим позже правильно (через прокси/внешний слой)
}


def _normalize_offer(src: str, offer: Offer) -> Optional[Offer]:
    """
    Приводим оффер к единому формату и отбрасываем мусор.
    """
    try:
        title = str(offer.get("title", "")).strip()
        url = str(offer.get("url", "")).strip()
        price = int(offer.get("price", 0))
        if not title or not url or price <= 0:
            return None
        offer["title"] = title
        offer["url"] = url
        offer["price"] = price
        offer["source"] = str(offer.get("source", src))
        return offer
    except Exception:
        return None


def fetch_offers(query: str, limit: int = 10) -> List[Offer]:
    """
    Единая точка входа “как OpenClaw”:
    - вызывает все источники
    - нормализует
    - склеивает
    - сортирует по цене
    """
    all_offers: List[Offer] = []

    for src_name, fn in SOURCES.items():
        try:
            items = fn(query, limit)
            for it in items:
                norm = _normalize_offer(src_name, it)
                if norm:
                    all_offers.append(norm)
        except Exception as e:
            # НЕ падаем — просто добавим "ошибку" как оффер, чтобы было видно в телеге
            all_offers.append({
                "title": f"[{src_name}] ошибка: {type(e).__name__}",
                "price": 10**18,
                "url": "about:blank",
                "source": src_name,
            })

    all_offers.sort(key=lambda x: int(x.get("price", 10**18)))
    return all_offers[:limit]
