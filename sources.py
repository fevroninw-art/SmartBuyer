def fetch_stub(query: str) -> list[dict]:
    return [
        {"title": f"{query} (вариант 1)", "price": 79990, "url": "https://example.com/1", "source": "stub"},
        {"title": f"{query} (вариант 2)", "price": 82990, "url": "https://example.com/2", "source": "stub"},
        {"title": f"{query} (вариант 3)", "price": 85990, "url": "https://example.com/3", "source": "stub"},
    ]
