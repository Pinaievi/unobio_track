
def render_md(report: dict, claims_file: str) -> str:
    L = []
    L.append(f"# Investment Underwriting Report: {report['drug']} in "
             f"{report['indication']}\n")
    L.append(f"*Generated: {report['generated']}. Claims used: "
             f"{len(report['claims'])}. Run cost: ~${report['cost']['usd']:.4f}.*\n")
    if any(c.get("source_type") == "demo_synthetic" for c in report["claims"]):
        L.append("> ⚠ **DEMO:** цей звіт містить СИНТЕТИЧНІ докази "
                 "(source_type demo_synthetic), вигадані лише для перевірки "
                 "конвеєра. Це не реальні дані.\n")
    L.append("Legend: **[E]** = restates evidence, **[AI]** = AI inference. "
             f"Ids in brackets are claim ids; every claim with its exact quote is in "
             f"`{claims_file}`.\n")

    def stmts(items):
        for s in items:
            tag = "E" if s["kind"] == "evidence" else "AI"
            cites = ", ".join(s["claim_ids"] + s.get("evidence_ids", [])) \
                or "no claims"
            warn = (f" ⚠ unverified numbers: {s['unverified_numbers']}"
                    if s.get("unverified_numbers") else "")
            L.append(f"- **[{tag}]** {s['text']} _[{cites}]_{warn}")
        L.append("")

    def gaps(sec):
        if sec["gaps"]:
            L.append("_Gaps in the data:_ " + "; ".join(sec["gaps"]) + "\n")

    L.append(f"## 1. Recommendation: {report['recommendation']}\n")
    stmts(report["recommendation_rationale"])
    n = 2
    for key in ["scientific_thesis", "translation_thesis", "clinical_plan",
                "competitive_landscape", "commercial_opportunity"]:
        sec = report["sections"][key]
        L.append(f"## {n}. {sec['title']}\n")
        stmts(sec["statements"])
        gaps(sec)
        n += 1
    L.append(f"## {n}. Capital to next milestone\n")
    stmts(report["capital_to_next_milestone"])
    n += 1
    sec = report["sections"]["key_risks"]
    L.append(f"## {n}. {sec['title']}\n")
    stmts(sec["statements"])
    gaps(sec)
    n += 1
    L.append(f"## {n}. Contradictory evidence\n")
    if report["conflicts"]:
        for c in report["conflicts"]:
            L.append(f"- **{c['topic']}** ({c['status']}; endpoint: "
                     f"{c.get('endpoint', '?')}; comparator: "
                     f"{c.get('shared_comparator', '?')})  \n"
                     f"  supports: {', '.join(c['supporting'])}; "
                     f"contradicts: {', '.join(c['contradicting'])}  \n"
                     f"  **[AI]** {c['assessment']}")
        L.append("")
    else:
        L.append("No conflicts between supporting and contradicting claims were "
                 "identified.\n")
    n += 1
    L.append(f"## {n}. Critical unknowns\n")
    for u in report["critical_unknowns"]:
        L.append(f"- {u}")
    L.append("")
    n += 1
    L.append(f"## {n}. Diligence questions\n")
    for i, q in enumerate(report["diligence_questions"], 1):
        L.append(f"{i}. {q}")
    L.append("")
    n += 1
    L.append(f"## {n}. What would change the conclusion\n")
    for w in report["what_would_change_the_conclusion"]:
        L.append(f"- {w}")
    L.append("")
    n += 1
    L.append(f"## {n}. Sources\n")
    for s in report["sources"]:
        link = f"<{s['url']}>" if s.get("url") else ""
        L.append(f"- **{s['evidence_id']}** ({s['source_type']}) {s['title']} "
                 f"{link} — claims: {', '.join(s['claim_ids']) or '—'}")
    if report.get("issues"):
        L.append("\n## Automatic checks\n")
        for i in report["issues"]:
            L.append(f"- {i}")
    return "\n".join(L) + "\n"

def render_claims_md(report: dict) -> str:
    L = [f"# Claims appendix: {report['drug']} in {report['indication']}\n",
         "Each claim with its exact quote from the source record.\n"]
    for c in report["claims"]:
        mark = " (NEW EVIDENCE)" if c.get("is_extra") else ""
        if c.get("source_type") == "demo_synthetic":
            mark += " (SYNTHETIC DEMO, NOT REAL DATA)"
        L.append(f"- **{c['id']}**{mark} [{c['stage']} / {c['direction']} / "
                 f"{c['confidence']}] {c['claim']}  \n  record: {c['evidence_id']}"
                 f"  \n  quote: \"{c['quote']}\""
                 + (f"  \n  ⚠ numbers not in the quote (found elsewhere in the "
                    f"record): {c['numbers_outside_quote']}"
                    if c.get("numbers_outside_quote") else "")
        + (f"\n  ℹ claim про інший препарат {c['reclassified_other_drug']}: "
           f"позначено як нейтральний competition"
           if c.get("reclassified_other_drug") else "")
                 + ("  \n  ⚠ drug name is in the claim but not in the quote "
                    "(attribution not verified)" if c.get("drug_not_in_quote") else ""))
    return "\n".join(L) + "\n"
