import re
from typing import Optional, Tuple


def parse_follow(text_after_keyword: str) -> Optional[Tuple[str, int]]:
    """
    Принимает строку ПОСЛЕ слова "следи".
    Примеры:
      "айфон до 90000" -> ("айфон", 90000)
      "ps5 50000"      -> ("ps5", 50000)
      "iphone 15 до 85к" -> ("iphone 15", 85000)
    """
    s = (text_after_keyword or "").strip()
    if not s:
        return None

    # поддержка "85к" / "85K"
    s_norm = s.replace("к", "000").replace("K", "000")

    nums = re.findall(r"\d+", s_norm)
    if not nums:
        return None

    limit = int(nums[-1])

    # убираем числа и слово "до"
    query = re.sub(r"\d+", " ", s_norm)
    query = re.sub(r"\bдо\b", " ", query, flags=re.IGNORECASE)
    query = " ".join(query.split()).strip()

    if not query:
        return None

    return query, limit
