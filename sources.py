# sources.py
from __future__ import annotations

from typing import List, Dict, Optional
import httpx

# Включать/выключать Avito можно переменной окружения (на будущее)
# AVITO_ENABLED = os.environ.get("AVITO_ENABLED", "0") == "1"


def fetch_stub(query: str) -> List[Dict]:
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1", "source": "stub"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2", "source": "stub"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3", "source": "stub"},
    ]


async def fetch_avito_async(query: str, max_items: int = 10) -> List[Dict]:
    """
    Пока: безопасная заготовка.
    Здесь позже добавим реальный парсинг/агрегацию Avito.
    Сейчас возвращаем пусто, чтобы не ломать бота.
    """
    return []


def fetch_avito(query: str, max_items: int = 10) -> List[Dict]:
    """
    Синхронная обёртка на будущее.
    Сейчас — просто пустой список.
    """
    return []


def fetch_offers(query: str, max_items: int = 10) -> List[Dict]:
    """
    Единая точка получения офферов для bot.py
    Сейчас: stub + (пока отключённый) avito.
    """
    offers: List[Dict] = []
    offers.extend(fetch_stub(query))

    # Когда будем готовы — включим:
    # try:
    #     offers.extend(fetch_avito(query, max_items=max_items))
    # except Exception:
    #     pass

    return offers[:max_items]
