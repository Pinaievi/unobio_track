"""
main.py — запускає весь конвеєр по черзі:

  1. datagetter/delegator.py       збір даних з усіх джерел
  2. datagetter/split_evidence.py  розбиття на частини в datagetter/results
  3. json-to-text.py               обробка частин і збирання звіту

Запуск:
  python main.py                              # препарат за замовчуванням (retatrutide)
  python main.py amycretin                    # один аргумент = препарат
  python main.py "obesity" "semaglutide"      # хвороба + препарат
  python main.py amycretin --skip-fetch       # не збирати дані заново, взяти готові

Аргументи (крім --skip-fetch) передаються в delegator.py як є.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATAGETTER = ROOT / "datagetters"

FETCH_SCRIPT = DATAGETTER / "delegator.py"
SPLIT_SCRIPT = DATAGETTER / "split_evidence.py"
TEXT_SCRIPT = ROOT / "json-to-text.py"


def run_step(title: str, script: Path, args: list[str], cwd: Path) -> None:
    """Запускає один крок. У разі помилки зупиняє весь конвеєр."""
    if not script.exists():
        print(f"\nНе знайдено файл: {script}")
        sys.exit(1)

    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")
    started = time.time()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"   # щоб кирилиця не ламалася в консолі Windows

    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
    )

    seconds = round(time.time() - started, 1)
    if result.returncode != 0:
        print(f"\nКрок «{title}» завершився з помилкою (код {result.returncode}). Далі не йдемо.")
        sys.exit(result.returncode)
    print(f"\nГотово за {seconds} с")


def main() -> None:
    args = sys.argv[1:]

    skip_fetch = "--skip-fetch" in args
    args = [a for a in args if a != "--skip-fetch"]

    total_started = time.time()

    if skip_fetch:
        print("Крок 1 пропущено (--skip-fetch): використовуємо вже зібраний evidence_raw.json")
    else:
        run_step("Крок 1/3: збір даних (delegator.py)", FETCH_SCRIPT, args, DATAGETTER)

    run_step("Крок 2/3: розбиття на частини (split_evidence.py)", SPLIT_SCRIPT, [], DATAGETTER)
    run_step("Крок 3/3: обробка і звіт (json-to-text.py)", TEXT_SCRIPT, [], ROOT)

    print(f"\nВесь конвеєр виконано за {round(time.time() - total_started, 1)} с")


if __name__ == "__main__":
    main()
