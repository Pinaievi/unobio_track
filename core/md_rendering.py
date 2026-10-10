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
    if report.get("red_flags"):
        who = report.get("critical_rule_applied_by")
        by_model = report.get("recommendation_by_model")
        if who == "code":
            step = (f" The model proposed **{by_model}**; the code lowered it to "
                    f"**{report['recommendation']}**.")
        else:
            step = (f" The model applied the rule itself and recommended "
                    f"**{report['recommendation']}**; the code only checked it.")
        L.append("> 🚩 **Critical-finding rule.** A separate severity review (a model call, "
                 "with a keyword backstop) rated these findings as able to stop the "
                 "programme on their own:")
        for f in report["red_flags"]:
            cat = f" [{f['category']}]" if f.get("category") else ""
            L.append(f"> - {f['id']} (found by {' + '.join(f.get('found_by', []))}){cat}: "
                     f"{f.get('reason', '')}")
        L.append(f">\n> Policy: a critical finding that stops the programme (death, regulatory "
                 f"halt, termination, failed pivotal trial, invalid key result) gives Do Not Invest; "
                 f"any other critical finding lowers the recommendation by one level.{step}\n")
    gate = report.get("invest_gate") or {}
    if gate.get("checked") and not gate.get("passed"):
        L.append("> ⚖ **Invest gate.** The model proposed Invest, but the code lowered it to "
                 "Conditional: " + "; ".join(gate.get("reasons", [])) + ".\n")
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
    if report.get("catalyst_calendar"):
        L.append(f"## {n}. Catalyst calendar\n")
        stmts(report["catalyst_statements"])
        rows = report["catalyst_calendar"]["rows"]
        if rows:
            L.append("| Date | Event | Trial | Phase | Status | Sponsor | Primary endpoint / programme |")
            L.append("|---|---|---|---|---|---|---|")
            for r in rows:
                who = "competitor" if r["scope"] == "competitor" else "this drug"
                ind = "" if r.get("in_indication", True) else " (other indication)"
                L.append(f"| {r['date'] or '—'} | {r['kind']}{ind} ({who}) | {r['nct'] or '—'} | "
                         f"{r['phase']} | {r['status']} | {r['sponsor'] or '—'} | "
                         f"{(r['primary_outcome'] or '—')[:90]} |")
            L.append("")
        n += 1
    if report.get("pos"):
        L.append(f"## {n}. Probability of success (benchmark)\n")
        stmts(report["pos_statements"])
        pos = report["pos"]
        if pos["rows"] and pos["stage"] not in ("unknown", "approved_or_phase4"):
            L.append("| Benchmark | Phase 1→2 | Phase 2→3 | Phase 3→NDA/BLA | NDA/BLA→approval | PoS to approval from current stage |")
            L.append("|---|---|---|---|---|---|")
            for r in pos["rows"]:
                sr = r["stage_rates"]
                L.append(f"| {r['benchmark']} | {sr['p1']*100:.1f}% | {sr['p2']*100:.1f}% | "
                         f"{sr['p3']*100:.1f}% | {sr['nda']*100:.1f}% | "
                         f"**{r['pos_to_approval']*100:.0f}%** |")
            L.append(f"\nSource: {pos['source']}\n")
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
                 f"  \n  region: {c.get('region', 'Global')}"
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