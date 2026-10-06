"""
delegator.py — запускає всі data getters паралельно та збирає результат.

Запуск:
  python delegator.py                                  # retatrutide за замовчуванням
  python delegator.py tirzepatide                      # один аргумент = препарат
  python delegator.py "Alzheimer disease" "BACE1 inhibitor"   # хвороба + препарат

Результат: evidence_raw.json поруч із цим файлом.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from getters import DataGetter, Query, discover

GETTER_TIMEOUT = 90  # секунд на одне джерело
OUTPUT_PATH = Path(__file__).resolve().parent / "evidence_raw.json"

DEFAULT_INDICATION = ""
DEFAULT_MECHANISM = "retatrutide"


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

    # дедуплікація за id
    seen, unique = set(), []
    for rec in evidence:
        if rec["id"] not in seen:
            seen.add(rec["id"])
            unique.append(rec)

    return {
        "input": {"indication": query.indication, "mechanism": query.mechanism},
        "total_seconds": round(time.time() - started, 2),
        "trace": trace,
        "evidence": unique,
    }


def parse_args(args: list[str]) -> tuple[str, str]:
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
        print("Потрібно вказати принаймні хворобу або препарат.")
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

    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nУсього унікальних записів: {len(result['evidence'])}")
    print(f"Збережено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()