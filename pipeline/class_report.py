"""
class_report.py — class-level roll-up of per-drug underwriting reports.

Input : results/report_<drug>.json for every member of the class (made by main.py).
Output: results/class_<class>.json and results/class_<class>.md

The class verdict is NOT written by the model. It is a transparent rule over the member
verdicts, so it can be checked by reading the table:
  - every member "Do Not Invest"        -> Do Not Invest
  - every member "Invest"               -> Invest
  - anything else (members disagree, or any member is Conditional) -> Conditional
A signal that appears in 2+ members (the same critical-finding category) is reported as a
class-wide signal, because it points at the mechanism and not at one molecule.

Run:  python pipeline/class_report.py --class "BTK inhibitor" --indication "multiple sclerosis" \
          --members "tolebrutinib,fenebrutinib" [--failed "drugX"]
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.config import slug  # noqa: E402

RESULTS = ROOT / "results"

LEVELS = ["Do Not Invest", "Conditional", "Invest"]


def class_verdict(recs: list[str]) -> str:
    if recs and all(r == "Do Not Invest" for r in recs):
        return "Do Not Invest"
    if recs and all(r == "Invest" for r in recs):
        return "Invest"
    return "Conditional"


def member_summary(name: str) -> dict | None:
    path = RESULTS / f"report_{slug(name)}.json"
    if not path.exists():
        return None
    rep = json.loads(path.read_text(encoding="utf-8"))
    claims = {c["id"]: c for c in rep.get("claims", [])}
    flags = [{"id": f["id"], "category": f.get("category"), "reason": f.get("reason", ""),
              "claim": (claims.get(f["id"]) or {}).get("claim") or f.get("claim", ""),
              "evidence_id": (claims.get(f["id"]) or {}).get("evidence_id")}
             for f in rep.get("red_flags", [])]
    gate = rep.get("invest_gate") or {}
    return {
        "drug": rep.get("drug", name), "report": path.name,
        "recommendation": rep.get("recommendation"),
        "recommendation_by_model": rep.get("recommendation_by_model"),
        "claims": len(rep.get("claims", [])),
        "sources": len(rep.get("sources", [])),
        "conflicts": len(rep.get("conflicts", [])),
        "critical_findings": flags,
        "invest_gate_reasons": gate.get("reasons", []) if gate.get("checked") and not gate.get("passed") else [],
        "top_statements": [s for s in rep.get("recommendation_rationale", [])[:3]],
        "what_would_change": rep.get("what_would_change_the_conclusion", [])[:3],
        "generated": rep.get("generated"),
    }


def build(class_text: str, indication: str, members: list[str], failed: list[str]) -> dict:
    rows, missing = [], []
    for m in members:
        s = member_summary(m)
        (rows if s else missing).append(s or m)

    recs = [r["recommendation"] for r in rows]
    by_cat = defaultdict(list)
    for r in rows:
        for f in r["critical_findings"]:
            by_cat[f["category"]].append((r["drug"], f))
    class_wide = [{"category": cat, "drugs": sorted({d for d, _ in items}),
                   "examples": [{"drug": d, "id": f["id"], "reason": f["reason"]}
                                for d, f in items[:3]]}
                  for cat, items in by_cat.items() if len({d for d, _ in items}) >= 2]
    counts = {lvl: recs.count(lvl) for lvl in LEVELS}
    verdict = class_verdict(recs) if rows else None
    return {
        "kind": "class", "class": class_text, "indication": indication,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recommendation": verdict, "rule": "all Do Not Invest -> Do Not Invest; all Invest -> "
        "Invest; otherwise Conditional (rule over member verdicts, not a model judgement)",
        "counts": counts, "members": rows, "failed": failed + [m for m in missing if m not in failed],
        "members_total": len(members), "partial": len(rows) < len(members),
        "class_wide_signals": class_wide,
    }


def render_md(c: dict) -> str:
    out = [f"# Class underwriting: {c['class']} in {c['indication']}", "",
           f"**Class verdict: {c['recommendation']}**  ",
           f"Rule: {c['rule']}.  ", f"Generated {c['generated']}", "",
           "## Members", "",
           "| Drug | Verdict | Claims | Sources | Critical findings | Report |",
           "|---|---|---|---|---|---|"]
    for r in c["members"]:
        crit = "; ".join(f"{f['id']} ({f['category']})" for f in r["critical_findings"]) or "—"
        out.append(f"| {r['drug']} | {r['recommendation']} | {r['claims']} | {r['sources']} | "
                   f"{crit} | {r['report']} |")
    if c["failed"]:
        out += ["", "Members without a report (run failed or not run): " + ", ".join(c["failed"])]
    if c["partial"]:
        out += ["", f"**Partial verdict: based on {len(c['members'])} of {c['members_total']} "
                    "members. Re-run the missing ones before relying on it.**"]
    out += ["", "## Class-wide signals", ""]
    if c["class_wide_signals"]:
        for s in c["class_wide_signals"]:
            out.append(f"- **{s['category']}** appears in {len(s['drugs'])} members "
                       f"({', '.join(s['drugs'])}), so it points at the mechanism, not one molecule:")
            for e in s["examples"]:
                out.append(f"  - {e['drug']} {e['id']}: {e['reason']}")
    else:
        out.append("No critical-finding category repeats across 2+ members.")
    out += ["", "## Why each member got its verdict", ""]
    for r in c["members"]:
        out.append(f"### {r['drug']} — {r['recommendation']}")
        if r["recommendation_by_model"] and r["recommendation_by_model"] != r["recommendation"]:
            out.append(f"_The model proposed {r['recommendation_by_model']}; the code lowered it._")
        for f in r["critical_findings"]:
            out.append(f"- Critical {f['id']} ({f['category']}): {f['reason']}")
        for g in r["invest_gate_reasons"]:
            out.append(f"- Invest gate: {g}")
        for s in r["top_statements"]:
            tag = "[E]" if s.get("kind") == "evidence" else "[AI]"
            out.append(f"- {tag} {s['text']} ({', '.join(s.get('claim_ids', []))})")
        if r["what_would_change"]:
            out.append("- What would change it: " + " / ".join(r["what_would_change"]))
        out.append("")
    out.append("Drill-down: open any report above (Recommendation → Claims → Evidence → Sources).")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="class_text", required=True)
    ap.add_argument("--indication", required=True)
    ap.add_argument("--members", required=True, help="comma-separated drug names")
    ap.add_argument("--failed", default="", help="comma-separated drugs whose run failed")
    args = ap.parse_args()

    members = [m.strip() for m in args.members.split(",") if m.strip()]
    failed = [m.strip() for m in args.failed.split(",") if m.strip()]
    c = build(args.class_text, args.indication, members, failed)
    if not c["members"]:
        sys.exit("No member reports found in results/. Run the per-drug pipeline first.")
    stem = f"class_{slug(args.class_text)}"
    (RESULTS / f"{stem}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / f"{stem}.md").write_text(render_md(c), encoding="utf-8")
    print(f"Class verdict: {c['recommendation']}  {c['counts']}")
    print(f"Saved: results/{stem}.md and results/{stem}.json")


if __name__ == "__main__":
    main()