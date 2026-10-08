"""
check_claims.py — перевірка результату витягування фактів.

Запуск (з кореня проєкту):
  python check_claims.py
або з явними шляхами:
  python check_claims.py results/output0.json results/evidence
(перший аргумент — файл із claims, другий — папка з evidence_part_*.json)
"""

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

claims_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/claims.json")
parts_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results/evidence")

MAX_QUOTE_LEN = 300   # ліміт довжини цитати з промпта

# Записи про випробування: claim зазвичай описує кілька полів запису (фаза, статус,
# кількість учасників), тому «числа є в записі, але не в цитаті» там нормально.
TRIAL_KINDS = {"nct", "nct_aact", "nct_aact_population", "nct_aact_flow", "nct_aact_pk"}

# Додаткові записи AACT: за правилами промпта цитата для них береться з поля text.
COMPANION_KINDS = {"nct_aact_population", "nct_aact_flow", "nct_aact_pk"}

# Етапи, відсутність яких означає прогалину в даних («other» — звичайна смітниця).
REQUIRED_STAGES = ["unmet_need", "mechanism", "translation", "clinical",
                   "competition", "regulatory", "safety_or_failure"]

QUERY_TAGS = ["base_search", "contradiction_search", "pk_search",
              "tissue_search", "epidemiology_search"]


# ---------- допоміжні функції ----------

def norm(text: str) -> str:
    """Суворе порівняння: пробіли й регістр не враховуємо."""
    return re.sub(r"\s+", " ", text).strip().lower()


def squash(text: str) -> str:
    """Лояльне порівняння: приводимо спецсимволи до звичайних (m² -> m2, I² -> I2),
    потім лишаємо лише літери й цифри (лапки, коми, дефіси ігноруємо)."""
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\W_]+", "", text)


def quote_ok(quote: str, target_squashed: str) -> bool:
    """Цитата перевірена, якщо кожен її шматок є в цільовому тексті.
    Розділювачі шматків: '...' та маркер пункту списку '*' (так записані критерії
    відбору). Шматки коротші за 8 символів ігноруємо, щоб одне слово не давало
    хибного збігу."""
    pieces = [p for p in re.split(r"\.{3}|…|(?:^|\s)\*\s", quote) if len(squash(p)) >= 8]
    return bool(pieces) and all(squash(p) in target_squashed for p in pieces)


def canon(n: str) -> str:
    """Канонічний вигляд числа, щоб 30.0 і 30 вважались однаковими:
    30.0 -> 30, 27.50 -> 27.5, 40.0 -> 40."""
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def numbers(text: str) -> set[str]:
    """Числа з тексту: десяткові або від двох цифр.
    Номери випробувань (NCT...) ігноруємо; розділювачі тисяч прибираємо (10,000 -> 10000);
    десяткову крапку '·' (як у Lancet) приводимо до звичайної;
    кінцеві нулі після крапки відкидаємо (30.0 -> 30)."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"NCT\d+", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    found = (canon(n.replace("·", ".")) for n in re.findall(r"\d+(?:[.·]\d+)?", text))
    return {n for n in found if "." in n or len(n) >= 2}


def is_year(n: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", n))


def claim_text(c: dict) -> str:
    return c.get("claim") or c.get("text") or ""


def show(label: str, items: list[dict], limit: int = 5) -> None:
    """Друкує приклади claims для перевірки очима."""
    if not items:
        return
    print(f"\n{label} (перші {min(limit, len(items))} із {len(items)}):")
    for c in items[:limit]:
        print(f"  [{c.get('evidence_id')}] {claim_text(c)}")


# ---------- читаємо записи з частин ----------

recs: dict[str, dict] = {}
for path in sorted(parts_dir.glob("evidence_part_*.json")):
    for rec in json.loads(path.read_text(encoding="utf-8"))["evidence"]:
        dumped = json.dumps(rec, ensure_ascii=False, indent=2)
        meta = rec.get("meta") or {}
        found_all = meta.get("found_by_all") or ([meta["found_by"]] if meta.get("found_by") else [])
        recs[rec["id"]] = {
            "strict": norm(dumped),
            "loose": squash(dumped),
            "text_loose": squash(rec.get("text") or ""),
            "numbers": numbers(dumped),
            "kind": rec.get("source_type", "?"),
            "title": rec.get("title", ""),
            "text_len": len(rec.get("text") or ""),
            "found_by_all": found_all,
        }

if not recs:
    print(f"Записів не знайдено. Перевір папку: {parts_dir.resolve()}")
    print("Там мають лежати файли evidence_part_*.json (їх створює split_evidence.py).")
    sys.exit(1)

claims = json.loads(claims_path.read_text(encoding="utf-8"))["claims"]

# ---------- рахуємо ----------

per_record = Counter(c.get("evidence_id") for c in claims)
unknown_ids = [c for c in claims if c.get("evidence_id") not in recs]
known = [c for c in claims if c.get("evidence_id") in recs]

not_strict = [c for c in known if norm(c.get("quote", "")) not in recs[c["evidence_id"]]["strict"]]
suspicious = [c for c in known if not quote_ok(c.get("quote", ""), recs[c["evidence_id"]]["loose"])]
no_claims = [rid for rid in recs if rid not in per_record]
weak = [c for c in claims if len(c.get("quote", "")) < 15]
too_long = [c for c in claims if len(c.get("quote", "")) > MAX_QUOTE_LEN]
dots = [c for c in claims if "..." in c.get("quote", "") or "…" in c.get("quote", "")]

# перевірка за числами
num_not_in_record = []      # числа, яких немає в записі взагалі: можлива вигадка
num_not_in_quote = []       # числа є в записі, але не в цитаті (лише для не-випробувань)
trial_wide = 0              # те саме для випробувань: очікувано, лише рахуємо
for c in known:
    r = recs[c["evidence_id"]]
    claim_nums = numbers(claim_text(c))
    miss_record = sorted(claim_nums - r["numbers"])
    miss_quote = sorted(n for n in claim_nums - numbers(c.get("quote", "")) if not is_year(n))
    if miss_record:
        num_not_in_record.append((c, miss_record))
    elif miss_quote:
        if r["kind"] in TRIAL_KINDS:
            trial_wide += 1
        else:
            num_not_in_quote.append((c, miss_quote))

# ---------- загальні показники ----------

print(f"Записів: {len(recs)}")
print(f"Claims: {len(claims)} (в середньому {len(claims) / len(recs):.1f} на запис)")
print(f"Записів без жодного claim: {len(no_claims)}")
print(f"Claims із посиланням на неіснуючий id: {len(unknown_ids)}")
print(f"Цитата не знайдена дослівно: {len(not_strict)}")
print(f"Цитат зі склейкою через '...': {len(dots)}")
print(f"Справді підозрілі цитати (не знайдено навіть по шматках): {len(suspicious)}")
print(f"Цитат довших за {MAX_QUOTE_LEN} символів: {len(too_long)}")
print(f"Дуже коротких цитат (менше 15 символів): {len(weak)}")
print(f"Claims із числами, яких НЕМАЄ в записі (можлива вигадка): {len(num_not_in_record)}")
print(f"Claims зі статей, де числа є в записі, але не в цитаті: {len(num_not_in_quote)}")
print(f"Claims про випробування з числами поза цитатою (нормально): {trial_wide}")

# ---------- джерела ----------

print("\nДжерело: записів -> claims")
kind_records = Counter(r["kind"] for r in recs.values())
for source, n_rec in kind_records.most_common():
    n_cl = sum(1 for c in known if recs[c["evidence_id"]]["kind"] == source)
    print(f"  {source:<22} {n_rec:>3} -> {n_cl:>3}  ({n_cl / n_rec:.1f} на запис)")

# ---------- віддача кожного запиту Europe PMC ----------

tag_records, tag_claims = Counter(), Counter()
for r in recs.values():
    for t in r["found_by_all"]:
        tag_records[t] += 1
for c in known:
    for t in recs[c["evidence_id"]]["found_by_all"]:
        tag_claims[t] += 1

if tag_records:
    print("\nВіддача запитів Europe PMC: статей -> claims")
    for tag in QUERY_TAGS:
        if tag in tag_records:
            flag = "   <- запит приніс статті, але жодного claim (шум?)" if tag_claims[tag] == 0 else ""
            print(f"  {tag:<22} {tag_records[tag]:>3} -> {tag_claims[tag]:>3}{flag}")

# ---------- етапи й напрямки ----------

print("\nClaims за етапом і напрямком (0 означає прогалину в даних):")
stage_counts = Counter(c.get("stage") for c in claims)
for stage in REQUIRED_STAGES + [s for s in stage_counts if s not in REQUIRED_STAGES]:
    n = stage_counts.get(stage, 0)
    dirs = Counter(c.get("direction") for c in claims if c.get("stage") == stage)
    detail = ", ".join(f"{d}: {k}" for d, k in dirs.most_common()) or "—"
    mark = "  <- ПРОГАЛИНА" if n == 0 and stage in REQUIRED_STAGES else ""
    print(f"  {n:>4}  {stage:<18} ({detail}){mark}")

contradicts = sum(1 for c in claims if c.get("direction") == "contradicts")
from_contra = [c for c in known if "contradiction_search" in recs[c["evidence_id"]]["found_by_all"]]
print(f"\nClaims із напрямком 'contradicts': {contradicts}")
print(f"Записів із пошуку суперечностей: {tag_records.get('contradiction_search', 0)}, "
      f"claims із них: {len(from_contra)}")

# ---------- перевірка правил із промпта ----------

preprint_high = [c for c in known
                 if recs[c["evidence_id"]]["kind"] == "epmc_ppr" and c.get("confidence") == "high"]
pk_tissue_high = [c for c in known
                  if set(recs[c["evidence_id"]]["found_by_all"]) & {"pk_search", "tissue_search"}
                  and c.get("stage") == "translation" and c.get("confidence") == "high"]
companion_not_text = [c for c in known
                      if recs[c["evidence_id"]]["kind"] in COMPANION_KINDS
                      and not quote_ok(c.get("quote", ""), recs[c["evidence_id"]]["text_loose"])]
pk_wrong_stage = [c for c in known
                  if recs[c["evidence_id"]]["kind"] == "nct_aact_pk" and c.get("stage") != "translation"]

print("\nПеревірка правил промпта:")
print(f"  Препринти з confidence 'high' (мають бути medium/low): {len(preprint_high)}")
print(f"  Етап translation із pk/tissue-запитів з confidence 'high' (перевір очима): {len(pk_tissue_high)}")
print(f"  Claims по записах AACT, цитата яких не з поля text: {len(companion_not_text)}")
print(f"  Фармакокінетика AACT не з етапом translation: {len(pk_wrong_stage)}")

# ---------- записи без claims ----------

with_text = [rid for rid in no_claims if recs[rid]["text_len"] > 0]
without_text = [rid for rid in no_claims if recs[rid]["text_len"] == 0]
if with_text:
    print(f"\nЗапис має текст, але claims немає ({len(with_text)}): перевір, чи не пропущено важливе")
    for rid in with_text:
        r = recs[rid]
        print(f"  [{r['kind']}] ({r['text_len']} симв.) {r['title'][:75]}")
if without_text:
    print(f"\nЗаписи без тексту (немає анотації), пропуск виправданий ({len(without_text)}):")
    for rid in without_text:
        r = recs[rid]
        print(f"  [{r['kind']}] {r['title'][:75]}")

# ---------- приклади для перевірки очима ----------

if num_not_in_record:
    print("\nЧисла, яких немає в записі (найпідозріліше):")
    for c, miss in num_not_in_record[:10]:
        print(f"\n  [{c.get('evidence_id')}] claim: {claim_text(c)}")
        print(f"  чисел немає в записі: {', '.join(miss)}")

if num_not_in_quote:
    print("\nClaim зі статті ширший за цитату, перші 10:")
    for c, miss in num_not_in_quote[:10]:
        print(f"\n  [{c.get('evidence_id')}] claim: {claim_text(c)}")
        print(f"  чисел немає в цитаті: {', '.join(miss)}")

show("Препринти з confidence 'high'", preprint_high)
show("Translation із pk/tissue-запитів з 'high'", pk_tissue_high)
show("Цитата не з поля text у записі AACT", companion_not_text)

if too_long:
    print(f"\nЦитати довші за {MAX_QUOTE_LEN} символів (довжина, початок), перші 5:")
    for c in too_long[:5]:
        q = c.get("quote", "")
        print(f"  [{c.get('evidence_id')}] {len(q)} симв.: {q[:100]}...")

if suspicious:
    print("\nПідозрілі цитати, цілком:")
    for c in suspicious[:10]:
        print(f"\n  [{c.get('evidence_id')}] claim: {claim_text(c)}")
        print(f"  цитата: {c.get('quote', '')}")