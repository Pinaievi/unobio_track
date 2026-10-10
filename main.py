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
    print("SITE: report drill-down")
    print("  " + " ".join(cmd))
    print("=" * 70, flush=True)
    if dry:
        return
    if not app.exists():
        print(f"{app} not found, site not started.")
        return
    try:
        import streamlit
    except ImportError:
        print("Streamlit is not installed. Run: pip install streamlit\n"
              "then: python main.py --ui-only")
        return
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["UNDERWRITING_REPORT"] = report_name
    print("The site will open in the browser (http://localhost:8501). "
          "Stop with Ctrl+C.", flush=True)
    try:
        subprocess.call(cmd, cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print("\nSite stopped.")


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
        print(f"  Removed old evidence parts: {len(old)}")


def run_step(name: str, cmd: list, dry: bool) -> float:
    print("\n" + "=" * 70)
    print(f"STEP: {name}")
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
        sys.exit(f"\nStep \"{name}\" failed (exit code {code}). "
                 f"Pipeline stopped.")
    print(f"\nStep \"{name}\" finished in {dt:.1f} s")
    return dt


def print_summary(out_prefix: str, timings: dict, start_ts: str):
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, dt in timings.items():
        print(f"  {name:<8} {dt:>7.1f} s")
    print(f"  {'total':<8} {sum(timings.values()):>7.1f} s")

    path = RESULTS / f"{out_prefix or 'report'}.json"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    print(f"\n  Recommendation: {rep.get('recommendation')}")
    print(f"  Claims in report: {len(rep.get('claims', []))}")
    print(f"  Evidence conflicts: {len(rep.get('conflicts', []))}")

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
                g = "claim extraction" if str(e.get("step", "")).startswith("claims:") \
                    else "report"
                s = groups.setdefault(g, [0, 0, 0, 0.0])
                s[0] += 1
                s[1] += e.get("input_tokens", 0)
                s[2] += e.get("output_tokens", 0)
                s[3] += e.get("cost_usd", 0.0)
        print("\n  LLM cost for this run (prices in the files are placeholders):")
        total = 0.0
        for g, (n, tin, tout, usd) in groups.items():
            print(f"    {g:<16} calls {n:>3}, tokens {tin} / {tout}, ~${usd:.4f}")
            total += usd
        print(f"    {'total':<16} ~${total:.4f}")
    print(f"\n  Report: results/{path.stem}.md")
    print(f"  Claims: results/{path.stem}_claims.md")
    print(f"  Logs:   results/run_log.jsonl")


def main():
    ap = argparse.ArgumentParser(description="Run the whole underwriting pipeline")
    ap.add_argument("--drug", default=None, help="drug (default: retatrutide)")
    ap.add_argument("--indication", default=None, help="indication (default: obesity)")
    ap.add_argument("--from", dest="start", choices=STEPS, default="fetch",
                    help="start from this step (earlier steps are skipped)")
    ap.add_argument("--only", choices=STEPS, default=None, help="run only this step")
    ap.add_argument("--extra", default=None, help="file with new claims (for the demo)")
    ap.add_argument("--out-prefix", default=None, help="output report name, e.g. report_new")
    ap.add_argument("--compare", default=None, help="previous report.json to compare against")
    ap.add_argument("--workers", type=int, default=None,
                    help="threads for claim extraction (default: as in claim_collector; "
                         "set 2 if the API returns 429)")
    ap.add_argument("--no-ui", action="store_true",
                    help="do not open the report site after the pipeline")
    ap.add_argument("--ui-only", action="store_true",
                    help="only open the site (do not run the pipeline)")
    ap.add_argument("--dry-run", action="store_true", help="only show the commands")
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
            sys.exit(f"{script} not found. Run main.py from the project root.")

    print(f"Drug: {args.drug or 'retatrutide (default)'}, "
          f"indication: {args.indication or 'obesity (default)'}")
    print("Steps: " + " -> ".join(steps))

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