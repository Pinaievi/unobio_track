"""
  python demo.py ui        open the site (class view, per-drug reports)
  python demo.py rollup    rebuild the BTK-inhibitor class report from finished drug reports (free, seconds)
  python demo.py fene      step 1: new POSITIVE evidence for fenebrutinib (Phase III readouts) -> report_fenebrutinib_new
  python demo.py fene2     step 2: then CONTRADICTORY evidence (fatal cases reported) -> report_fenebrutinib_deaths
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

CLASS = "BTK inhibitor"
INDICATION = "multiple sclerosis"
MEMBERS = "tolebrutinib,evobrutinib,fenebrutinib,orelabrutinib,pirtobrutinib"

# step: (drug, evidence file, output prefix, report to compare against)
NEW_EVIDENCE = {
    "fene": ("fenebrutinib", "extra_claims_real_fenebrutinib_positive.json",
             "report_fenebrutinib_new", "report_fenebrutinib"),
    "fene2": ("fenebrutinib", "extra_claims_real_fenebrutinib.json",
              "report_fenebrutinib_deaths", "report_fenebrutinib_new"),
    "tole": ("tolebrutinib", "extra_claims_real_tolebrutinib_crl.json",
             "report_tolebrutinib_new", "report_tolebrutinib"),
}


def run(cmd: list, dry: bool) -> None:
    parts = [str(c).replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "") for c in cmd[1:]]
    shown = " ".join(f'"{c}"' if " " in c else c for c in ["python"] + parts)
    print(f"\n$ {shown}\n", flush=True)
    if dry:
        return
    code = subprocess.call(cmd, cwd=ROOT)
    if code:
        sys.exit(code)


def find_file(name: str) -> Path:
    for folder in (ROOT, ROOT / "results", Path.cwd()):
        if (folder / name).exists():
            return folder / name
    sys.exit(f"File {name} not found. Put it next to demo.py.")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry"]
    dry = "--dry" in sys.argv
    step = args[0] if args else ""
    py, main_py = sys.executable, str(ROOT / "main.py")

    if step == "ui":
        run([py, main_py, "--ui-only"], dry)
    elif step == "rollup":
        run([py, main_py, "--drug", CLASS, "--indication", INDICATION,
             "--drugs", MEMBERS, "--rollup-only", "--no-ui"], dry)
    elif step in NEW_EVIDENCE:
        drug, fname, out_prefix, before = NEW_EVIDENCE[step]
        extra = find_file(fname)
        old = ROOT / "results" / f"{before}.json"
        if not old.exists():
            sys.exit(f"{old.name} not found: run the previous step first "
                     f"(the 'before' report must exist).")
        print(f"Restoring the saved data of {drug} (no API calls)...")
        if not dry:
            import main as pipeline_main
            if not pipeline_main.restore_drug(drug):
                sys.exit(f"No saved data for {drug} in results/drugs/{drug}/")
        run([py, main_py, "--drug", drug, "--indication", INDICATION, "--only", "report",
             "--extra", str(extra), "--out-prefix", out_prefix,
             "--compare", str(old), "--no-ui"], dry)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()