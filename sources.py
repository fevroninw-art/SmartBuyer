def fetch_avito(query: str, *, max_items: int = 10) -> List[Dict]:
    q = quote_plus(query)
    url = f"https://m.avito.ru/api/1/items?q={q}&limit={max_items}"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    try:
        r = httpx.get(url, headers=headers, timeout=15.0)
    except Exception:
        return []

    if r.status_code != 200:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    out: List[Dict] = []

    items = data.get("items", [])
    for it in items:
        title = it.get("title")
        price = it.get("price")
        link = it.get("url")

        if not title or not price or not link:
            continue

        if isinstance(link, str) and link.startswith("/"):
            link = "https://www.avito.ru" + link

        try:
            price_int = int(price)
        except Exception:
            continue

        out.append({
            "title": title,
            "price": price_int,
            "url": link,
            "source": "avito"
        })

    return out
