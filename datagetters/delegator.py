"""
delegator.py — запускає всі data getters паралельно й збирає результат.

Запуск:
  python delegator.py                                         # препарат за замовчуванням (retatrutide)
  python delegator.py tirzepatide                             # один аргумент = препарат
  python delegator.py "Alzheimer disease" "BACE1 inhibitor"   # хвороба + препарат

Результат: unobio_track/results/evidence_raw.json
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from getters import DataGetter, Query, discover

GETTER_TIMEOUT = 90  # секунд на одне джерело

# Корінь проєкту = папка, що лежить над папкою з getters (unobio_track).
ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
OUTPUT_PATH = RESULTS_DIR / "evidence_raw.json"

DEFAULT_INDICATION = ""
DEFAULT_MECHANISM = "retatrutide"

# Джерела, що описують одні й ті самі випробування (ключ дубля = номер NCT).
# Чим більше число, тим бажаніша версія запису: в AACT є результати (p-value, інтервали).
TRIAL_SOURCE_PRIORITY = {"nct_aact": 2, "nct": 1}


def dedupe(evidence: list[dict]) -> tuple[list[dict], int]:
    """Прибирає дублі. Повертає (список без дублів, скільки прибрано).

    1. Записи з однаковим id — дубль (одна стаття знайшлася двома запитами).
    2. Випробування з однаковим номером NCT з різних баз — дубль.
       Лишається версія з вищим пріоритетом (AACT багатша за ClinicalTrials).
       У полі meta.also_found_in зберігається, в яких іще базах воно знайшлося.
    Порядок записів зберігається.
    """
    best: dict[str, dict] = {}       # ключ дубля -> найкращий запис
    order: list[str] = []            # порядок першої появи ключів
    also_in: dict[str, list[str]] = {}   # ключ -> джерела, де знайшлося те саме випробування

    for rec in evidence:
        if rec["source_type"] in TRIAL_SOURCE_PRIORITY:
            key = f"trial:{rec['source_id']}"
            priority = TRIAL_SOURCE_PRIORITY[rec["source_type"]]
        else:
            key = f"id:{rec['id']}"
            priority = 0

        if key not in best:
            best[key] = rec
            order.append(key)
            also_in[key] = []
            continue

        # дубль: лишаємо запис із вищим пріоритетом, іншого запам'ятовуємо
        current = best[key]
        current_priority = TRIAL_SOURCE_PRIORITY.get(current["source_type"], 0)
        if priority > current_priority:
            loser, best[key] = current, rec
        else:
            loser = rec
        if key.startswith("trial:"):
            also_in[key].append(loser["source_type"])

    unique = []
    for key in order:
        rec = best[key]
        if also_in[key]:
            rec["meta"]["also_found_in"] = sorted(set(also_in[key]))
        unique.append(rec)

    return unique, len(evidence) - len(unique)


def run(query: Query, getters: list[DataGetter] | None = None) -> dict:
    getters = getters or discover()
    started = time.time()

    def timed_fetch(getter: DataGetter):
        t0 = time.time()
        records = getter.fetch(query)
        return records, time.time() - t0

    executor = ThreadPoolExecutor(max_workers=len(getters))
    futures = {g.name: executor.submit(timed_fetch, g) for g in getters}

    evidence: list[dict] = []
    trace: list[dict] = []

    for name, future in futures.items():
        try:
            records, seconds = future.result(timeout=GETTER_TIMEOUT)
            for rec in records:
                rec["meta"]["getter"] = name
            evidence += records
            trace.append({"getter": name, "ok": True,
                          "count": len(records), "seconds": round(seconds, 2)})
        except Exception as e:  # одне джерело, що впало, не валить решту
            trace.append({"getter": name, "ok": False,
                          "error": f"{type(e).__name__}: {e}"})

    executor.shutdown(wait=False, cancel_futures=True)

    unique, removed = dedupe(evidence)

    # друга фаза: getters, що вміють уточнювати результат за даними інших джерел
    # (edgar бере спонсора з реєстру випробувань і замінює запис із ручної таблиці)
    for g in getters:
        refine = getattr(g, "refine", None)
        if refine is None:
            continue
        try:
            out = refine(query, unique)
            if out is not None:
                new_records, replace_types = out
                unique = [r for r in unique if r["source_type"] not in replace_types]
                for rec in new_records:
                    rec["meta"]["getter"] = g.name
                unique += new_records
                trace.append({"getter": f"{g.name}:refine", "ok": True,
                              "count": len(new_records), "seconds": 0})
        except Exception as e:
            trace.append({"getter": f"{g.name}:refine", "ok": False,
                          "error": f"{type(e).__name__}: {e}"})

    return {
        "input": {"indication": query.indication, "mechanism": query.mechanism},
        "total_seconds": round(time.time() - started, 2),
        "duplicates_removed": removed,
        "trace": trace,
        "evidence": unique,
    }


def parse_args(args: list[str]) -> tuple[str, str]:
    """Розбирає аргументи командного рядка: (хвороба, препарат)."""
    args = [a.strip() for a in args]
    if len(args) == 0:
        return DEFAULT_INDICATION, DEFAULT_MECHANISM
    if len(args) == 1:          # лише препарат
        return "", args[0]
    if len(args) == 2:          # хвороба + препарат
        return args[0], args[1]
    print('Використання:\n'
          '  python delegator.py                      (за замовчуванням)\n'
          '  python delegator.py "<препарат>"\n'
          '  python delegator.py "<хвороба>" "<препарат>"')
    sys.exit(1)


def main() -> None:
    indication, mechanism = parse_args(sys.argv[1:])

    if not indication and not mechanism:
        print("Потрібно вказати хоча б хворобу або препарат.")
        sys.exit(1)

    print(f"Запит: indication={indication!r}, mechanism={mechanism!r}")
    result = run(Query(indication=indication, mechanism=mechanism))

    print("\nДжерело            Статус   Записів   Секунд")
    print("-" * 50)
    for t in result["trace"]:
        if t["ok"]:
            print(f"{t['getter']:<18} ok       {t['count']:>7}   {t['seconds']:>6}")
        else:
            print(f"{t['getter']:<18} ПОМИЛКА  {t['error']}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)   # створюємо results/, якщо її ще немає
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nДублів прибрано: {result['duplicates_removed']}")
    print(f"Усього унікальних записів: {len(result['evidence'])}")
    print(f"Збережено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()