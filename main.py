"""
main.py — запускає весь конвеєр від запиту до фінального звіту.

Кроки:
  1. fetch   — datagetters/delegator.py     (збір доказів із 5 джерел -> results/evidence_raw.json)
  2. split   — datagetters/split_evidence.py (розбиття на частини -> results/evidence/)
  3. claims  — claim_collector.py            (витяг фактів через LLM -> results/claims.json)
  4. report  — build_report.py               (звіт -> results/report.md, report.json)
  5. ui      — app.py (Streamlit)             (drill-down сайт зі звітом; відкривається сам)

Приклади (з кореня проєкту):
  python main.py                                     # ретатрутид, ожиріння (за замовчуванням)
  python main.py --drug retatrutide --indication obesity
  python main.py --from claims                       # зібрані докази вже є, почати з витягу фактів
  python main.py --only report                       # лише перебудувати звіт
  python main.py --only report --extra extra_claims.json --out-prefix report_new \
                 --compare results/report.json       # демо «нові докази змінюють висновок»
  python main.py --no-ui                             # не відкривати сайт після конвеєра
  python main.py --ui-only                           # лише відкрити сайт для наявних звітів
  python main.py --dry-run                           # показати команди, нічого не запускаючи

Після кроків конвеєра сайт відкривається автоматично (зупинити: Ctrl+C у консолі).
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
STEPS = ["fetch", "split", "claims", "report"]


def build_commands(args) -> dict:
    """Команда для кожного кроку. Усі запускаються з кореня проєкту."""
    py = sys.executable

    fetch = [py, str(ROOT / "datagetters" / "delegator.py")]
    if args.indication and args.drug:
        fetch += [args.indication, args.drug]
    elif args.drug:
        fetch += [args.drug]

    report = [py, str(ROOT / "pipeline" / "build_report.py")]
    if args.drug:
        report += ["--drug", args.drug]
    if args.indication:
        report += ["--indication", args.indication]
    if args.extra:
        report += ["--extra", args.extra]
    if args.out_prefix:
        report += ["--out-prefix", args.out_prefix]
    if args.compare:
        report += ["--compare", args.compare]

    claims = [py, str(ROOT / "pipeline" / "claim_collector.py")]
    if args.workers:
        claims += ["--workers", str(args.workers)]

    return {
        "fetch": fetch,
        "split": [py, str(ROOT / "datagetters" / "split_evidence.py")],
        "claims": claims,
        "report": report,
    }


def launch_ui(report_name: str, dry: bool):
    """Запускає Streamlit-сайт (app.py) і відкриває вибраний звіт.
    Блокує консоль, поки користувач не натисне Ctrl+C."""
    app = ROOT / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app)]
    print("\n" + "=" * 70)
    print("САЙТ: drill-down звіту")
    print("  " + " ".join(cmd))
    print("=" * 70, flush=True)
    if dry:
        return
    if not app.exists():
        print(f"Не знайдено {app}, сайт не запущено.")
        return
    try:
        import streamlit
    except ImportError:
        print("Streamlit не встановлено. Виконай: pip install streamlit\n"
              "потім: python main.py --ui-only")
        return
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["UNDERWRITING_REPORT"] = report_name
    print("Сайт відкриється в браузері (http://localhost:8501). "
          "Зупинити: Ctrl+C.", flush=True)
    try:
        subprocess.call(cmd, cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print("\nСайт зупинено.")


def clean_old_parts():
    """Прибираємо старі частини evidence, щоб після нового збору не лишилось
    зайвих файлів від попереднього запуску (інакше в claims потраплять застарілі записи)."""
    folder = RESULTS / "evidence"
    if not folder.exists():
        return
    old = list(folder.glob("evidence_part_*.json"))
    for p in old:
        p.unlink()
    if old:
        print(f"  Прибрано старих частин evidence: {len(old)}")


def run_step(name: str, cmd: list, dry: bool) -> float:
    print("\n" + "=" * 70)
    print(f"КРОК: {name}")
    print("  " + " ".join(cmd))
    print("=" * 70, flush=True)
    if dry:
        return 0.0

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    t0 = time.time()
    code = subprocess.call(cmd, cwd=str(ROOT), env=env)
    dt = time.time() - t0
    if code != 0:
        sys.exit(f"\nКрок «{name}» завершився з помилкою (код {code}). "
                 f"Конвеєр зупинено.")
    print(f"\nКрок «{name}» завершено за {dt:.1f} с")
    return dt


def print_summary(out_prefix: str, timings: dict, start_ts: str):
    print("\n" + "=" * 70)
    print("ПІДСУМОК")
    print("=" * 70)
    for name, dt in timings.items():
        print(f"  {name:<8} {dt:>7.1f} с")
    print(f"  {'разом':<8} {sum(timings.values()):>7.1f} с")

    path = RESULTS / f"{out_prefix or 'report'}.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    print(f"\n  Рекомендація: {rep.get('recommendation')}")
    print(f"  Claims у звіті: {len(rep.get('claims', []))}")
    print(f"  Конфліктів доказів: {len(rep.get('conflicts', []))}")

    log_path = RESULTS / "run_log.jsonl"
    if log_path.exists():
        groups = {}
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("ts", "") < start_ts:
                    continue
                g = "витяг фактів" if str(e.get("step", "")).startswith("claims:") \
                    else "звіт"
                s = groups.setdefault(g, [0, 0, 0, 0.0])
                s[0] += 1
                s[1] += e.get("input_tokens", 0)
                s[2] += e.get("output_tokens", 0)
                s[3] += e.get("cost_usd", 0.0)
        print("\n  Вартість LLM за цей запуск (ціни в файлах — заглушки):")
        total = 0.0
        for g, (n, tin, tout, usd) in groups.items():
            print(f"    {g:<14} викликів {n:>3}, токени {tin} / {tout}, ~${usd:.4f}")
            total += usd
        print(f"    {'разом':<14} ~${total:.4f}")
    print(f"\n  Звіт:   results/{path.stem}.md")
    print(f"  Claims: results/{path.stem}_claims.md")
    print(f"  Логи:   results/run_log.jsonl")


def main():
    ap = argparse.ArgumentParser(description="Запуск усього конвеєра андеррайтингу")
    ap.add_argument("--drug", default=None, help="препарат (за замовчуванням retatrutide)")
    ap.add_argument("--indication", default=None, help="показання (за замовчуванням obesity)")
    ap.add_argument("--from", dest="start", choices=STEPS, default="fetch",
                    help="почати з цього кроку (попередні пропускаються)")
    ap.add_argument("--only", choices=STEPS, default=None, help="виконати лише цей крок")
    ap.add_argument("--extra", default=None, help="файл з новими claims (для демо)")
    ap.add_argument("--out-prefix", default=None, help="ім'я вихідного звіту, напр. report_new")
    ap.add_argument("--compare", default=None, help="попередній report.json для порівняння")
    ap.add_argument("--workers", type=int, default=None,
                    help="потоків для витягу фактів (за замовчуванням як у claim_collector; "
                         "став 2, якщо API відповідає 429)")
    ap.add_argument("--no-ui", action="store_true",
                    help="не відкривати сайт зі звітом після конвеєра")
    ap.add_argument("--ui-only", action="store_true",
                    help="лише відкрити сайт (конвеєр не запускати)")
    ap.add_argument("--dry-run", action="store_true", help="лише показати команди")
    args = ap.parse_args()

    report_name = f"{args.out_prefix or 'report'}.json"
    if args.ui_only:
        launch_ui(report_name, args.dry_run)
        return

    if args.only:
        steps = [args.only]
    else:
        steps = STEPS[STEPS.index(args.start):]

    cmds = build_commands(args)

    for s in steps:
        script = Path(cmds[s][1])
        if not script.exists():
            sys.exit(f"Не знайдено {script}. Запускай main.py з кореня проєкту.")

    print(f"Препарат: {args.drug or 'retatrutide (за замовчуванням)'}, "
          f"показання: {args.indication or 'obesity (за замовчуванням)'}")
    print("Кроки: " + " -> ".join(steps))

    start_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    timings = {}
    for s in steps:
        if s == "split" and not args.dry_run:
            clean_old_parts()
        timings[s] = run_step(s, cmds[s], args.dry_run)

    if not args.dry_run:
        print_summary(args.out_prefix, timings, start_ts)
    if not args.no_ui:
        launch_ui(report_name, args.dry_run)


if __name__ == "__main__":
    main()