import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

claims_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/output0.json")
parts_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("datagetters/results")

TRIAL_KINDS = {"nct", "nct_aact"}


def norm(text: str) -> str:
    """Суворе порівняння: пробіли й регістр не враховуємо."""
    return re.sub(r"\s+", " ", text).strip().lower()


def squash(text: str) -> str:
    """Лояльне порівняння: приводимо спецсимволи до звичайних (m² -> m2, I² -> I2),
    потім лишаємо лише літери й цифри (лапки, коми, дефіси ігноруємо)."""
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\W_]+", "", text)


def quote_ok(quote: str, record_squashed: str) -> bool:
    """Цитата перевірена, якщо кожен її шматок (між '...') є в записі.
    Шматки коротші за 8 символів ігноруємо, щоб одне слово не давало хибного збігу."""
    pieces = [p for p in re.split(r"\.{3}|…", quote) if len(squash(p)) >= 8]
    return bool(pieces) and all(squash(p) in record_squashed for p in pieces)


def numbers(text: str) -> set[str]:
    """Числа з тексту: десяткові або від двох цифр.
    Номери випробувань (NCT...) ігноруємо; розділювачі тисяч прибираємо (10,000 -> 10000);
    десяткову крапку '·' (як у Lancet) приводимо до звичайної."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"NCT\d+", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    found = (n.replace("·", ".") for n in re.findall(r"\d+(?:[.·]\d+)?", text))
    return {n for n in found if "." in n or len(n) >= 2}


def claim_text(c: dict) -> str:
    return c.get("claim") or c.get("text") or ""


# --- читаємо записи з частин ---
strict, loose, kinds, titles, found_by, text_len, rec_numbers = {}, {}, {}, {}, {}, {}, {}
for path in sorted(parts_dir.glob("evidence_part_*.json")):
    for rec in json.loads(path.read_text(encoding="utf-8"))["evidence"]:
        dumped = json.dumps(rec, ensure_ascii=False, indent=2)
        rid = rec["id"]
        strict[rid] = norm(dumped)
        loose[rid] = squash(dumped)
        rec_numbers[rid] = numbers(dumped)
        kinds[rid] = rec.get("source_type", "?")
        titles[rid] = rec.get("title", "")
        text_len[rid] = len(rec.get("text") or "")
        found_by[rid] = (rec.get("meta") or {}).get("found_by")

claims = json.loads(claims_path.read_text(encoding="utf-8"))["claims"]

# --- рахуємо ---
per_record = Counter(c.get("evidence_id") for c in claims)
unknown_ids = [c for c in claims if c.get("evidence_id") not in strict]
known = [c for c in claims if c.get("evidence_id") in strict]

not_strict = [c for c in known if norm(c.get("quote", "")) not in strict[c["evidence_id"]]]
suspicious = [c for c in known if not quote_ok(c.get("quote", ""), loose[c["evidence_id"]])]
no_claims = [rid for rid in strict if rid not in per_record]
weak = [c for c in claims if len(c.get("quote", "")) < 15]
dots = [c for c in claims if "..." in c.get("quote", "") or "…" in c.get("quote", "")]
# перевірка за числами
num_not_in_record = []      # числа, яких немає в записі взагалі: можлива вигадка
num_not_in_quote = []       # числа є в записі, але не в цитаті (лише для не-випробувань)
trial_wide = 0              # те саме для випробувань: очікувано, лише рахуємо
for c in known:
    claim_nums = numbers(claim_text(c))
    miss_record = sorted(claim_nums - rec_numbers[c["evidence_id"]])
    miss_quote = sorted(claim_nums - numbers(c.get("quote", "")))
    if miss_record:
        num_not_in_record.append((c, miss_record))
    elif miss_quote:
        if kinds[c["evidence_id"]] in TRIAL_KINDS:
            trial_wide += 1
        else:
            num_not_in_quote.append((c, miss_quote))

print(f"Записів: {len(strict)}")
print(f"Claims: {len(claims)} (в середньому {len(claims) / max(len(strict), 1):.1f} на запис)")
print(f"Записів без жодного claim: {len(no_claims)}")
print(f"Claims із посиланням на неіснуючий id: {len(unknown_ids)}")
print(f"Цитата не знайдена дослівно: {len(not_strict)}")
print(f"Цитат зі склейкою через '...': {len(dots)}")
print(f"Справді підозрілі цитати (не знайдено навіть по шматках): {len(suspicious)}")
print(f"Дуже коротких цитат (менше 15 символів): {len(weak)}")
print(f"Claims із числами, яких НЕМАЄ в записі (можлива вигадка): {len(num_not_in_record)}")
print(f"Claims зі статей, де числа є в записі, але не в цитаті: {len(num_not_in_quote)}")
print(f"Claims про випробування з числами поза цитатою (нормально): {trial_wide}")

print("\nДжерело: записів -> claims")
for source, n_rec in Counter(kinds.values()).most_common():
    n_cl = sum(1 for c in claims if kinds.get(c.get("evidence_id")) == source)
    print(f"  {source:<14} {n_rec:>3} -> {n_cl:>3}  ({n_cl / n_rec:.1f} на запис)")

print("\nClaims за етапом і напрямком:")
for stage, n in Counter(c.get("stage") for c in claims).most_common():
    dirs = Counter(c.get("direction") for c in claims if c.get("stage") == stage)
    print(f"  {n:>4}  {stage}  ({', '.join(f'{d}: {k}' for d, k in dirs.most_common())})")

contradicts = sum(1 for c in claims if c.get("direction") == "contradicts")
from_contra = [c for c in known if found_by.get(c["evidence_id"]) == "contradiction_search"]
n_contra_records = sum(1 for v in found_by.values() if v == "contradiction_search")
print(f"\nClaims із напрямком 'contradicts': {contradicts}")
print(f"Записів із пошуку суперечностей: {n_contra_records}, claims із них: {len(from_contra)}")

# записи без claims: спершу ті, де текст є (їх пропуск важливіший)
with_text = [rid for rid in no_claims if text_len[rid] > 0]
without_text = [rid for rid in no_claims if text_len[rid] == 0]
if with_text:
    print(f"\nЗапис має текст, але claims немає ({len(with_text)}): перевір, чи не пропущено важливе")
    for rid in with_text:
        print(f"  [{kinds[rid]}] ({text_len[rid]} симв.) {titles[rid][:75]}")
if without_text:
    print(f"\nЗаписи без тексту (немає анотації), пропуск виправданий ({len(without_text)}):")
    for rid in without_text:
        print(f"  [{kinds[rid]}] {titles[rid][:75]}")

if num_not_in_record:
    print("\nЧисла, яких немає в записі (найпідозріліше), перші 10:")
    for c, miss in num_not_in_record[:10]:
        print(f"\n  [{c.get('evidence_id')}] claim: {claim_text(c)}")
        print(f"  чисел немає в записі: {', '.join(miss)}")

if num_not_in_quote:
    print("\nClaim зі статті ширший за цитату, перші 10:")
    for c, miss in num_not_in_quote[:10]:
        print(f"\n  [{c.get('evidence_id')}] claim: {claim_text(c)}")
        print(f"  чисел немає в цитаті: {', '.join(miss)}")

if suspicious:
    print("\nПідозрілі цитати, цілком:")
    for c in suspicious[:10]:
        print(f"\n  [{c.get('evidence_id')}] claim: {claim_text(c)}")
        print(f"  цитата: {c.get('quote', '')}")