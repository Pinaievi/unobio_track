"""
main.py — запускає весь конвеєр від запиту до фінального звіту.

Кроки:
  1. fetch   — datagetters/delegator.py     (збір доказів із 5 джерел -> results/evidence_raw.json)
  2. split   — datagetters/split_evidence.py (розбиття на частини -> results/evidence/)
  3. claims  — claim_collector.py            (витяг фактів через LLM -> results/claims.json)
  4. report  — build_report.py               (звіт -> results/report.md, report.json)
  5. ui      — app.py (Streamlit)             (drill-down сайт зі звітом; відкривається сам)

Якщо --drug — це КЛАС ("BTK inhibitor", "GLP-1 receptor agonist"), main.py знаходить препарати
класу (datagetters/class_resolver.py), проганяє повний конвеєр для кожного (results/report_<препарат>.*,
дані кожного лежать в results/drugs/<препарат>/) і збирає звіт класу results/class_<клас>.*.
Препарат ніколи не вгадується: для збору даних потрібен --drug; кроки без збору
беруть препарат із results/evidence_raw.json і зупиняються, якщо --drug не збігається.

Приклади (з кореня проєкту):
  python main.py --drug retatrutide --indication obesity
  python main.py --drug tolebrutinib --indication "multiple sclerosis"
  python main.py --drug "BTK inhibitor" --indication "multiple sclerosis"   # клас: сам знаходить препарати
  python main.py --drug "BTK inhibitor" --indication "multiple sclerosis" --drugs "tolebrutinib,fenebrutinib"
  python main.py --drug "BTK inhibitor" --indication "multiple sclerosis" --only report   # клас з архіву, ~$0.02 за препарат
  python main.py --drug "BTK inhibitor" --indication "multiple sclerosis" --drugs "a,b,c" --rollup-only   # лише перезібрати звіт класу з готових report_<препарат>.json (безкоштовно)
  python main.py --from claims                       # зібрані докази вже є, почати з витягу фактів
  python main.py --only report                       # лише перебудувати звіт (для зібраного препарату)
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
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from core.config import fetched_target, looks_like_class, same_name, slug

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


ARCHIVE = RESULTS / "drugs"
ARCHIVED = ["evidence_raw.json", "claims.json"]


def archive_drug(name: str) -> None:
    """Save this drug's collected data so the class can be rebuilt later (report only)."""
    dest = ARCHIVE / slug(name)
    dest.mkdir(parents=True, exist_ok=True)
    for f in ARCHIVED:
        if (RESULTS / f).exists():
            shutil.copy2(RESULTS / f, dest / f)
    if (RESULTS / "evidence").exists():
        shutil.rmtree(dest / "evidence", ignore_errors=True)
        shutil.copytree(RESULTS / "evidence", dest / "evidence")


def restore_drug(name: str) -> bool:
    src = ARCHIVE / slug(name)
    if not (src / "evidence_raw.json").exists():
        return False
    for f in ARCHIVED:
        if (src / f).exists():
            shutil.copy2(src / f, RESULTS / f)
    if (src / "evidence").exists():
        shutil.rmtree(RESULTS / "evidence", ignore_errors=True)
        shutil.copytree(src / "evidence", RESULTS / "evidence")
    return True


def class_members(args, steps) -> list:
    """Drugs of the class: from --drugs, or found by class_resolver.py (or, when data is
    not re-collected, the list saved by the last resolver run)."""
    if args.drugs:
        return [d.strip().lower() for d in args.drugs.split(",") if d.strip()]
    saved = RESULTS / "class_members.json"
    if "fetch" not in steps:
        try:
            data = json.loads(saved.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if data and same_name(data.get("class"), args.drug):
            return [m["name"] for m in data.get("members", [])]
        sys.exit("No saved member list for this class. Run the full pipeline first, or pass "
                 "--drugs \"a,b,c\".")
    cmd = [sys.executable, str(ROOT / "datagetters" / "class_resolver.py"),
           args.drug, args.indication, "--max", str(args.max_drugs)]
    run_step("resolve class members", cmd, args.dry_run)
    if args.dry_run:
        return []
    data = json.loads(saved.read_text(encoding="utf-8"))
    return [m["name"] for m in data.get("members", [])]


def run_class(args, steps):
    """Class mode: the pipeline runs once per member drug; then the class report is built."""
    if not args.indication:
        sys.exit('A class needs an indication: --indication "multiple sclerosis"')
    if args.extra or args.compare:
        sys.exit("--extra / --compare work on one drug's report. Run them with --drug <drug>.")
    if steps[0] not in ("fetch", "report"):
        sys.exit("Class mode runs the full pipeline, or only the report step (--only report).")

    if args.rollup_only and not args.drugs:
        sys.exit('--rollup-only needs the member list: --drugs "a,b,c"')
    members = class_members(args, steps)
    if args.dry_run and not members:
        return None
    if not members:
        sys.exit("No drugs found for this class. Pass them yourself: --drugs \"a,b,c\"")
    print(f"\nClass '{args.drug}' in '{args.indication}' -> {len(members)} drug(s): "
          + ", ".join(members))

    failed = []
    for name in ([] if args.rollup_only else members):
        print("\n" + "#" * 70 + f"\n# DRUG: {name}\n" + "#" * 70)
        sub = argparse.Namespace(**vars(args))
        sub.drug, sub.out_prefix = name, f"report_{slug(name)}"
        cmds = build_commands(sub)
        try:
            if "fetch" not in steps and not args.dry_run and not restore_drug(name):
                sys.exit(f"No saved data for '{name}' in results/drugs/. Run the full pipeline first.")
            for s in steps:
                if s == "split" and not args.dry_run:
                    clean_old_parts()
                run_step(f"{s} [{name}]", cmds[s], args.dry_run)
            if "fetch" in steps and not args.dry_run:
                archive_drug(name)
        except SystemExit as e:
            failed.append(name)
            print(f"\n!! {name} failed: {e}\n   continuing with the next drug", flush=True)

    ok = [m for m in members if m not in failed]
    cmd = [sys.executable, str(ROOT / "pipeline" / "class_report.py"), "--class", args.drug,
           "--indication", args.indication, "--members", ",".join(members)]
    if failed:
        cmd += ["--failed", ",".join(failed)]
    run_step("class report", cmd, args.dry_run)
    if not ok and not args.dry_run:
        sys.exit("All drugs failed.")
    return f"class_{slug(args.drug)}.json"


def main():
    ap = argparse.ArgumentParser(description="Run the whole underwriting pipeline")
    ap.add_argument("--drug", default=None,
                    help="drug to underwrite (required when data is collected; otherwise "
                         "taken from results/evidence_raw.json)")
    ap.add_argument("--drugs", default=None,
                    help="class mode: comma-separated drugs of the class (skips automatic "
                         "discovery), e.g. \"tolebrutinib,fenebrutinib\"")
    ap.add_argument("--max-drugs", type=int, default=5,
                    help="class mode: how many drugs of the class to underwrite (default 5)")
    ap.add_argument("--rollup-only", action="store_true",
                    help="class mode: do not run any drug, only rebuild the class report from "
                         "the existing results/report_<drug>.json files (free)")
    ap.add_argument("--single", action="store_true",
                    help="treat --drug as one drug even if it reads like a class")
    ap.add_argument("--indication", default=None,
                    help="indication, e.g. \"multiple sclerosis\" (default: the one the "
                         "collected data was gathered for)")
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

    if looks_like_class(args.drug) and not args.single:
        print(f"'{args.drug}' reads like a drug class: underwriting its member drugs.")
        name = run_class(args, steps)
        if name and not args.dry_run:
            print(f"\n  Class report: results/{name[:-5]}.md")
            if not args.no_ui:
                launch_ui(name, False)
        return

    # The target drug is never assumed. Collecting data needs --drug. Steps that reuse
    # collected data take the drug from results/evidence_raw.json and refuse a different
    # --drug (otherwise old claims would be written up under the new drug's name).
    if "fetch" in steps:
        if not args.drug:
            sys.exit('Specify the drug, e.g.: python main.py --drug tolebrutinib '
                     '--indication "multiple sclerosis"')
    else:
        data_drug, data_ind = fetched_target(RESULTS)
        if not data_drug and not args.drug:
            sys.exit("No collected data in results/. First run: python main.py --drug <drug> "
                     "--indication \"<indication>\"")
        if args.drug and data_drug and not same_name(args.drug, data_drug):
            sys.exit(f"results/ holds data collected for '{data_drug}', not '{args.drug}'. "
                     f"Collect data for '{args.drug}' first: python main.py --drug "
                     f"\"{args.drug}\" --indication \"<indication>\"")
        args.drug = args.drug or data_drug
        if args.indication is None:
            args.indication = data_ind or ""
        elif data_ind and not same_name(args.indication, data_ind):
            print(f"Note: data was collected for indication '{data_ind}', "
                  f"the report uses '{args.indication}'.")

    cmds = build_commands(args)

    for s in steps:
        script = Path(cmds[s][1])
        if not script.exists():
            sys.exit(f"{script} not found. Run main.py from the project root.")

    print(f"Drug: {args.drug}, indication: {args.indication or '(not set)'}")
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