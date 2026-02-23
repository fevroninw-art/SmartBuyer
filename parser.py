import re
from typing import Optional, Tuple

def parse_follow(text: str) -> Optional[Tuple[str, int]]:
    """
    Принимает строку после слова "следи".
    Пример: "айфон до 90000" -> ("айфон", 90000)
    """
    s = text.strip()

    nums = re.findall(r"\d+", s)
    if not nums:
        return None

    limit = int(nums[-1])

    # убираем числа и слово "до"
    query = re.sub(r"\d+", "", s)
    query = re.sub(r"\bдо\b", "", query, flags=re.IGNORECASE).strip()

    if not query:
        return None

    return query, limit
