"""
split_evidence.py — ріже results/evidence_raw.json на частини за записами.

Запис (стаття / випробування) ніколи не розривається між файлами.
Частини лягають у results/evidence/ як evidence_part_001.json, 002 і так далі.

Запуск:
  python split_evidence.py          # ліміт 100 рядків
  python split_evidence.py 500      # власний ліміт рядків
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "results" / "evidence_raw.json"
PARTS_DIR = ROOT / "results" / "evidence"
DEFAULT_LINE_LIMIT = 100
HEADER_OVERHEAD = 12


def count_lines(record: dict) -> int:
    """Скільки рядків займе запис при збереженні з відступами."""
    return len(json.dumps(record, ensure_ascii=False, indent=2).splitlines())


def split_records(records: list[dict], line_limit: int) -> list[list[dict]]:
    chunks, current, current_lines = [], [], HEADER_OVERHEAD
    for rec in records:
        lines = count_lines(rec)
        if current and current_lines + lines > line_limit:
            chunks.append(current)
            current, current_lines = [], HEADER_OVERHEAD
        current.append(rec)
        current_lines += lines
    if current:
        chunks.append(current)
    return chunks


def main() -> None:
    line_limit = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LINE_LIMIT

    if not INPUT_PATH.exists():
        print(f"Немає файлу {INPUT_PATH}. Спочатку запусти delegator.py")
        sys.exit(1)

    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    records = data.get("evidence", [])
    if not records:
        print("У файлі немає записів evidence.")
        sys.exit(1)

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    for old in PARTS_DIR.glob("evidence_part_*.json"):
        old.unlink()

    chunks = split_records(records, line_limit)

    print(f"Записів: {len(records)}, ліміт: {line_limit} рядків, частин: {len(chunks)}\n")
    print("Файл                        Записів   Рядків")
    print("-" * 46)

    for n, chunk in enumerate(chunks, 1):
        payload = {
            "input": data.get("input"),
            "part": n,
            "total_parts": len(chunks),
            "evidence": chunk,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        path = PARTS_DIR / f"evidence_part_{n:03d}.json"
        path.write_text(text, encoding="utf-8")
        print(f"{path.name:<28}{len(chunk):>7}   {len(text.splitlines()):>6}")

    print(f"\nГотово. Частини лежать у {PARTS_DIR}")


if __name__ == "__main__":
    main()