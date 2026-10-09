import re
import unicodedata
import json

def read_all_text(path: str) -> str: 
    with open(path,"r") as f:
        return f.read()

def squash(text: str) -> str:
    """Лояльне порівняння: m² -> m2, потім лишаємо лише літери й цифри."""
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\W_]+", "", text)

def quote_ok(quote: str, target_squashed: str) -> bool:
    """Цитата перевірена, якщо кожен її шматок є в записі. Розділювачі шматків:
    '...' та маркер пункту списку '*'. Шматки коротші за 8 символів ігноруємо."""
    pieces = [p for p in re.split(r"\.{3}|…|(?:^|\s)\*\s", quote)
              if len(squash(p)) >= 8]
    return bool(pieces) and all(squash(p) in target_squashed for p in pieces)

def canon(n: str) -> str:
    """30.0 -> 30, 27.50 -> 27.5."""
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n

def find_key(obj, names):
    """Рекурсивно шукає перше непорожнє значення за одним із ключів (регістр і «_»
    ігноруються). Потрібно, бо meta у записів із різних джерел має різний вигляд."""
    want = {n.lower().replace("_", "") for n in names}
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                if str(k).lower().replace("_", "") in want and v not in (None, "", []):
                    return v
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None

def norm_status(v) -> str:
    return re.sub(r"[^A-Z]+", "_", str(v).upper()).strip("_") if v else ""

def norm_phase3(v) -> bool:
    """Phase 3 або Phase 2/Phase 3."""
    if not v:
        return False
    s = re.sub(r"[^A-Z0-9]", "", json.dumps(v, ensure_ascii=False).upper())
    return "PHASE3" in s

def norm_int(v):
    if isinstance(v, dict):
        v = v.get("count")
    try:
        n = int(float(str(v).replace(",", "").replace(" ", "")))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None

def clean_ids(text: str) -> str:
    """Прибираємо номери claims із вільного тексту (вони мають бути лише в claim_ids)."""
    return re.sub(r"(?i)\b(?:claims?\s+)?[CX]\d{3}\b", "a claim", text or "")

def percent_numbers(text: str) -> set:
    """Числа, після яких стоїть % (ключові факти, не роки й не номери)."""
    text = unicodedata.normalize("NFKC", strip_labels(text or ""))
    return {canon(n.replace("·", ".")) for n in
            re.findall(r"(\d+(?:[.·]\d+)?)\s*%", text)}

def strip_labels(text: str) -> str:
    """Перед перевіркою чисел прибираємо те, що числами фактів не є:
    id claims (C013) та назви фаз (Phase 3, Phase 3b)."""
    text = re.sub(r"\b[CX]\d{3}\b", " ", text)
    text = re.sub(r"(?i)\bphase\s*\d+\w*", " ", text)
    return text

def numbers(text: str) -> set:
    """Числа з тексту: десяткові або від двох цифр. NCT-номери ігноруємо,
    розділювачі тисяч прибираємо, '·' як десяткову крапку приводимо до '.'."""
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"NCT\d+", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    found = (canon(n.replace("·", ".")) for n in re.findall(r"\d+(?:[.·]\d+)?", text))
    return {n for n in found if "." in n or len(n) >= 2}