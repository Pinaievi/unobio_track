import argparse
import json
from datetime import date, datetime
import os
import re
import sys
import time
from pathlib import Path
from typing import Literal

import dotenv
from google import genai
from pydantic import BaseModel, Field
# Корінь проєкту = тека над pipeline/. Python за замовчуванням бачить лише теку скрипта
# (pipeline/), тому додаємо корінь і core/ у шлях імпорту вручну.
ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from prompts import *
from core.validation import *
from core.md_rendering import *
from core.evidence import *
from core.capital import *

MODEL = "gemini-3.1-flash-lite"      
FINAL_MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3

RESULTS = ROOT / "results"

ALIASES = {
    "retatrutide": ["LY3437943"],
    "maridebart cafraglutide": ["MariTide", "AMG 133"],
    "amycretin": ["NN9487"],
    "petrelintide": ["ZP8396"],
    "trontinemab": ["RO7126209", "RG6102"],
    "lepodisiran": ["LY3819469"],
    "zilebesiran": ["ALN-AGT01"],
    "sonelokimab": ["M1095", "ALX-0761"],
    "efruxifermin": ["AKR-001"],
    "divarasib": ["GDC-6036"],
    "frexalimab": ["SAR441344"],
    "duvakitug": ["TEV-48574", "SAR447189"],
    "elironrasib": ["RMC-6291"],
    "zoldonrasib": ["RMC-9805"],
    "verekitug": ["UPB-101"],
    "navenibart": ["STAR-0215"],
    "kt-474": ["SAR444656"],
    "mivelsiran": ["ALN-APP"],
    "hro761": ["HRO-761"],
}
INDICATION_SYNONYMS = {"obesity": ["overweight", "weight", "adipos", "bmi", "bariatric"]}

SECTIONS = [
    {
        "key": "scientific_thesis",
        "title": "Scientific thesis",
        "stages": ["mechanism", "other"],
        "task": "Why should {drug} work in {indication} biologically? Cover the target or "
                "pathway, genetic or experimental support, and what is NOT yet shown. "
                "Separate human data from animal and cell data.",
    },
    {
        "key": "translation_thesis",
        "title": "Human translation thesis",
        "stages": ["translation", "mechanism"],
        "task": "Is there evidence that {drug} reaches the target in humans at the doses "
                "used and that exposure relates to effect (PK, PD, target engagement, "
                "biomarkers)? State sample sizes and the quality of the source. Say "
                "plainly where human exposure data is thin or missing. Ex vivo tissue "
                "and cell data are not human exposure data.",
    },
    {
        "key": "clinical_plan",
        "title": "Clinical development plan",
        "stages": ["clinical", "regulatory"],
        "task": "Summarize the clinical programme of {drug} in {indication}: phases, "
                "designs, populations, comparators, reported efficacy results with effect "
                "sizes, and regulatory status. Then say what is the logical next step "
                "(inference) and what the programme still has to prove.",
    },
    {
        "key": "competitive_landscape",
        "title": "Competitive landscape",
        "stages": ["competition", "regulatory", "unmet_need"],
        "task": "Who else treats {indication} or targets the same pathway, according to "
                "the claims? Which ACTIVE comparators appear in trials of {drug}? Where "
                "is {drug} differentiated and where is that NOT supported by the claims? "
                "Do not name a competitor that does not appear in the claims. Do not "
                "treat placebo as a competitor.",
    },
    {
        "key": "commercial_opportunity",
        "title": "Commercial opportunity",
        "stages": ["unmet_need", "competition", "regulatory"],
        "task": "How large and how unmet is the need in {indication} according to the "
                "claims (prevalence, burden, standard of care)? What follows for "
                "{drug}'s commercial opportunity? There are no price or sales data in "
                "the claims, so market size in money must be marked as not estimable "
                "unless the claims contain it. Use only burden facts that bear on the "
                "indication itself.",
    },
    {
        "key": "key_risks",
        "title": "Key risks",
        "stages": ["safety_or_failure"],
        "include_all_contradicts": True,
        "task": "What are the main risks for {drug} in {indication}: safety signals, "
                "discontinuations, failed or stopped trials, weak or conflicting "
                "evidence, regulatory or quality problems? Rank them by importance to "
                "an investor and say which are single cases or spontaneous reports and "
                "therefore weak.",
    },
]

class Statement(BaseModel):
    text: str = Field(description="One or two sentences of the report text. "
                                  "Do not write claim ids inside the text.")
    kind: Literal["evidence", "inference"] = Field(
        description="evidence: restates what the cited claims say. "
                    "inference: your own reasoning built on the cited claims."
    )
    claim_ids: list[str] = Field(
        description="Ids of the claims (like C012) this statement is based on."
    )

class SectionDraft(BaseModel):
    statements: list[Statement]
    gaps: list[str] = Field(
        description="What is missing in the provided claims for this section."
    )

class FinalDraft(BaseModel):
    recommendation: Literal["Invest", "Conditional", "Do Not Invest"]
    recommendation_without_critical_findings: Literal["Invest", "Conditional", "Do Not Invest"] = Field(
        description="What you would recommend if the CRITICAL FINDINGS section did not "
                    "exist (judge all other evidence only). If it is 'none', repeat the "
                    "recommendation."
    )
    recommendation_rationale: list[Statement]
    critical_unknowns: list[str]
    diligence_questions: list[str] = Field(description="5 to 10 questions.")
    what_would_change_the_conclusion: list[str] = Field(
        description="Concrete new evidence that would move the recommendation up or down."
    )

class Runner:
    def __init__(self, client, log_path: Path):
        self.client = client
        self.log_path = log_path
        self.total_in = 0
        self.total_out = 0
        self.total_cost = 0.0
        self.calls = 0

    def call(self, step: str, model: str, prompt_text: str, schema_cls):
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.time()
            try:
                interaction = self.client.interactions.create(
                    model=model,
                    input=[{"type": "text", "text": prompt_text}],
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": schema_cls.model_json_schema(),
                    },
                )
                out = interaction.output_text
                parsed = schema_cls.model_validate_json(out)
                dt = time.time() - t0
                tin, tout, est = read_usage(interaction, prompt_text, out)
                cost = tin / 1e6 * PRICE_IN_PER_M + tout / 1e6 * PRICE_OUT_PER_M
                self.total_in += tin
                self.total_out += tout
                self.total_cost += cost
                self.calls += 1
                entry = {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "step": step, "model": model, "attempt": attempt,
                    "input_tokens": tin, "output_tokens": tout,
                    "tokens_estimated": est, "cost_usd": round(cost, 6),
                    "seconds": round(dt, 2),
                }
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                print(f"  [{step}] {dt:.1f} с, токени {tin}+{tout}"
                      f"{' (оцінка)' if est else ''}, ~${cost:.4f}")
                return parsed
            except Exception as e:
                last_err = e
                print(f"  [{step}] спроба {attempt} не вдалась: {e}")
                time.sleep(2 * attempt)
        raise RuntimeError(f"Крок {step} не вдався після {MAX_RETRIES} спроб: "
                           f"{last_err}")

def known_names_line(drug: str) -> str:
    """Рядок для промпту: інші назви того самого препарату (з конфігурації пошуку)."""
    names = ALIASES.get((drug or "").lower(), [])
    if not names:
        return ""
    return (f"KNOWN NAMES (search configuration, not evidence from the sources): "
            f"{drug} = {' = '.join(names)}. Treat them as the same drug.\n")

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def read_usage(interaction, prompt_text: str, out_text: str):
    """Токени з відповіді API; якщо поле не знайшлось — груба оцінка (довжина/4)."""
    usage = getattr(interaction, "usage", None) or getattr(
        interaction, "usage_metadata", None)
    tin = tout = None
    if usage is not None:
        for name in ("total_input_tokens", "input_tokens", "prompt_token_count"):
            v = getattr(usage, name, None)
            if isinstance(v, int):
                tin = v
                break
        for name in ("total_output_tokens", "output_tokens",
                     "candidates_token_count"):
            v = getattr(usage, name, None)
            if isinstance(v, int):
                tout = v
                break
    estimated = tin is None or tout is None
    if tin is None:
        tin = estimate_tokens(prompt_text)
    if tout is None:
        tout = estimate_tokens(out_text)
    return tin, tout, estimated

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drug", default="retatrutide")
    ap.add_argument("--indication", default="obesity")
    ap.add_argument("--claims", default=str(RESULTS / "claims.json"))
    ap.add_argument("--evidence", default=str(RESULTS / "evidence"))
    ap.add_argument("--extra", default=None,
                    help="JSON з новими claims (і, за потреби, evidence) для демо")
    ap.add_argument("--out-prefix", default="report")
    ap.add_argument("--compare", default=None,
                    help="шлях до попереднього report.json для порівняння висновків")
    args = ap.parse_args()

    dotenv.load_dotenv()
    key = os.environ.get("API_KEY")
    if not key:
        sys.exit("Немає API_KEY у .env")

    RESULTS.mkdir(exist_ok=True)
    log_path = RESULTS / "run_log.jsonl"

    print("1/5 Завантажую claims та записи...")
    evidence = load_evidence(Path(args.evidence))
    loose: dict = {}
    claims_raw = load_json(Path(args.claims)).get("claims", [])
    DRUG_NAMES.clear()
    DRUG_NAMES.update(n.lower() for n in
                      [args.drug] + ALIASES.get((args.drug or "").lower(), []) if n)
    INDICATION_WORDS.clear()
    for w in re.findall(r"[a-zA-Z]{4,}", (args.indication or "").lower()):
        INDICATION_WORDS.add(w[:6])
        INDICATION_WORDS.update(INDICATION_SYNONYMS.get(w, []))
    claims, dropped = prepare_claims(claims_raw, evidence, loose, "C")

    if args.extra:
        extra = load_json(Path(args.extra))
        for r in extra.get("evidence", []):
            evidence[r["id"]] = r
        ex_claims, ex_dropped = prepare_claims(extra.get("claims", []), evidence,
                                               loose, "X")
        claims += ex_claims
        dropped += ex_dropped
        print(f"  Нові докази з {args.extra}: додано {len(ex_claims)} claims")

    issues = [f"claim відкинуто ({d['reason']}): {d['claim'].get('claim', '')[:80]}"
              for d in dropped]
    with open(RESULTS / f"{args.out_prefix}_dropped_claims.json", "w",
              encoding="utf-8") as f:
        json.dump(dropped, f, ensure_ascii=False, indent=2)
    print(f"  Записів: {len(evidence)}, claims прийнято: {len(claims)}, "
          f"відкинуто: {len(dropped)}")
    if not claims:
        sys.exit("Немає жодного валідного claim.")
    claim_map = {c["id"]: c for c in claims}

    runner = Runner(genai.Client(api_key=key), log_path)
    ctx = {"drug": args.drug, "indication": args.indication}

    print("2/5 Етапні виклики (6)...")
    sections = {}
    for spec in SECTIONS:
        sel = [c for c in claims if c["stage"] in spec["stages"]
               or (spec.get("include_all_contradicts")
                   and c["direction"] == "contradicts")]
        if not sel:
            sections[spec["key"]] = {
                "title": spec["title"], "statements": [],
                "gaps": ["У наборі немає жодного claim для цього розділу."],
            }
            issues.append(f"{spec['title']}: немає claims — розділ порожній")
            print(f"  [{spec['key']}] claims немає, пропускаю")
            continue
        prompt = (COMMON_RULES
                  + f"\nSECTION: {spec['title']}\nTASK: "
                  + spec["task"].format(**ctx)
                  + f"\n\nDRUG: {args.drug}\nINDICATION: {args.indication}\n"
                  + known_names_line(args.drug) + "\n"
                  + "CLAIMS (one JSON per line):\n" + claims_for_prompt(sel))
        draft = runner.call(spec["key"], MODEL, prompt, SectionDraft)
        sections[spec["key"]] = {
            "title": spec["title"],
            "statements": validate_statements(draft.statements, claim_map,
                                              spec["title"], issues),
            "gaps": [strip_inline_ids(g) for g in draft.gaps],
        }

    drop_false_absence(sections, claim_map, issues)
    drop_false_h2h_absence(sections, [], claim_map, issues)

    # ключові результати ефективності, яких не взяв жоден розділ, код додає в клінічний план
    cited_now = {i for sec in sections.values() for st in sec["statements"]
                 for i in st["claim_ids"]}
    extra_eff = key_efficacy_items(claim_map, cited_now)
    if extra_eff and "clinical_plan" in sections:
        stm = sections["clinical_plan"]["statements"]
        last_e = max([k for k, x in enumerate(stm) if x["kind"] == "evidence"], default=-1)
        stm[last_e + 1:last_e + 1] = extra_eff
        issues.append("Clinical development plan: код додав ключові результати ефективності "
                      + ", ".join(x["claim_ids"][0] for x in extra_eff)
                      + " (жоден розділ їх не процитував)")

    ct = cross_trial_item(claim_map)
    if ct and "competitive_landscape" in sections:
        sections["competitive_landscape"]["statements"].append(ct)
        issues.append(f"Competitive landscape: код додав непряме порівняння ефективності "
                      f"{ct['claim_ids'][0]} vs {ct['claim_ids'][1]} (різні дослідження, не head-to-head)")

    cited = {i for sec in sections.values() for st in sec["statements"]
             for i in st["claim_ids"]}
    for c in claims:
        if c["direction"] in ("supports", "contradicts") and c["id"] not in cited \
                and c.get("confidence") != "low":
            issues.append(f"Покриття: claim {c['id']} ({c['direction']}, "
                          f"{c['stage']}) не використано в жодному розділі: "
                          f"{c['claim'][:80]}")

    print("3/5 Суперечності та капітал...")
    pro_con = [c for c in claims if c["direction"] in ("supports", "contradicts")]
    conflicts = []
    if any(c["direction"] == "contradicts" for c in pro_con) and \
            any(c["direction"] == "supports" for c in pro_con):
        cprompt = (CONFLICTS_TASK.format(drug=args.drug)
                   + "\nCLAIMS (one JSON per line):\n" + claims_for_prompt(pro_con))
        conflicts = validate_conflicts(
            runner.call("conflicts", MODEL, cprompt, ConflictsDraft),
            claim_map, issues)
    else:
        issues.append("Conflicts: немає claims з обома напрямками")

    capital_stmts, capital_calc = capital_from_registry(
        evidence, claims, claim_map, issues, args.drug, args.indication)

    print("4/5 Фінальна збірка...")
    counts = {}
    for c in claims:
        counts.setdefault(c["stage"], {}).setdefault(c["direction"], 0)
        counts[c["stage"]][c["direction"]] += 1
    sections_text = []
    for sec in sections.values():
        sections_text.append(f"## {sec['title']}")
        for s in sec["statements"]:
            sections_text.append(f"- [{s['kind']}] {s['text']} "
                                 f"[{', '.join(s['claim_ids'])}]")
        for g in sec["gaps"]:
            sections_text.append(f"- GAP: {g}")
    conflicts_text = "\n".join(
        f"- ({c['status']}) {c['topic']}: {c['assessment']} "
        f"[supports {', '.join(c['supporting'])}; "
        f"contradicts {', '.join(c['contradicting'])}]" for c in conflicts) \
        or "none identified"
    capital_text = "\n".join(f"- {s['text']}" for s in capital_stmts)
    contra = [c for c in claims if c["direction"] == "contradicts"]
    # тріаж тяжкості: модель сама оцінює, що критичне (без списку подій у коді)
    tri_pool = [c for c in claims if c["direction"] == "contradicts"
                or c["stage"] in ("safety_or_failure", "regulatory")]
    triage = []
    if tri_pool:
        print("  Тріаж тяжкості знахідок...")
        tprompt = (TRIAGE_TASK.format(**ctx) + known_names_line(args.drug)
                   + "\nCLAIMS (one JSON per line):\n" + claims_for_prompt(tri_pool))
        triage = validate_triage(runner.call("triage", MODEL, tprompt, TriageDraft),
                                 claim_map, issues)
    flags = merge_flags(triage, claim_map)
    flag_ids = {f["id"] for f in flags}
    flags_text = "\n".join(f"- {f['id']}: {f['reason']}: {f['claim']}" for f in flags) or "none"
    majors = [t for t in triage if t["level"] == "major"]
    if majors:
        flags_text += "\n(major, not critical: " + ", ".join(t["id"] for t in majors) + ")"
    final_prompt = (FINAL_TASK
                    + f"\nDRUG: {args.drug}\nINDICATION: {args.indication}\n"
                    + known_names_line(args.drug) + "\n"
                    + "CLAIM COUNTS BY STAGE AND DIRECTION:\n"
                    + json.dumps(counts, ensure_ascii=False)
                    + "\n\nDRAFTED SECTIONS:\n" + "\n".join(sections_text)
                    + "\n\nCONFLICTS:\n" + conflicts_text
                    + "\n\nCAPITAL ESTIMATE:\n" + capital_text
                    + "\n\nCRITICAL FINDINGS (rated by a separate severity review; a critical "
                      "finding can stop the programme on its own):\n" + flags_text
                    + "\nPOLICY: first fill recommendation_without_critical_findings (all "
                      "other evidence, ignoring the critical findings). If CRITICAL FINDINGS "
                      "is not 'none', your final recommendation must be one level lower than "
                      "that (Invest -> Conditional, Conditional -> Do Not Invest). Write the "
                      "rationale, critical_unknowns and what_would_change_the_conclusion for "
                      "your FINAL recommendation."                    + "\n\nALL CONTRADICTING CLAIMS:\n" + claims_for_prompt(contra))
    final = runner.call("final", FINAL_MODEL, final_prompt, FinalDraft)

    rationale = validate_statements(final.recommendation_rationale, claim_map,
                                    "Recommendation", issues, single_evidence=True)

    lead = lead_efficacy_item(claim_map)
    if lead and not any(x["kind"] == "evidence" and lead["claim_ids"][0] in x["claim_ids"]
                        for x in rationale):
        rationale.append(lead)
        issues.append(f"Recommendation: код додав головний результат ефективності "
                      f"{lead['claim_ids'][0]} (модель його не процитувала)")
    rationale = drop_false_h2h_absence({}, rationale, claim_map, issues)

    # червоні прапори й найважливіші нові докази мають бути в Recommendation як [E]
    have_e = {i for x in rationale if x["kind"] == "evidence" for i in x["claim_ids"]}
    for f in flags:
        if f["id"] not in have_e:
            rationale.append({"text": f["claim"], "kind": "evidence",
                              "claim_ids": [f["id"]], "unverified_numbers": []})
            issues.append(f"Recommendation: код додав критичну знахідку {f['id']} "
                          f"({f['kind']}, знайшов: {'+'.join(f['found_by'])}) — модель її не процитувала")
    for it in new_evidence_items(claim_map, rationale, flag_ids):
        rationale.append(it)
        issues.append(f"Recommendation: код додав нове свідчення {it['claim_ids'][0]} "
                      f"(is_extra) — воно має бути видно в рекомендації")
    rationale = order_rationale(rationale, claim_map, flag_ids)

    recommendation = final.recommendation
    model_recommendation = recommendation
    unresolved = [c for c in conflicts if c["status"] == "unresolved"]
    if recommendation == "Invest" and (final.critical_unknowns or unresolved):
        recommendation = "Conditional"
        issues.append("Рекомендацію «Invest» знижено до «Conditional»: "
                      "залишаються критичні невідомі або невирішені суперечності.")

    # правило наслідку: підтверджена критична знахідка знижує вивід на один рівень відносно
    # того, що модель сказала б БЕЗ неї. Що критичне — вирішує модель-тріаж (+ запасний
    # фільтр), не список у коді. Код лише перевіряє узгодженість двох відповідей моделі.
    rule_by = "none"
    if flags:
        who = "; ".join(f"{f['id']} ({'+'.join(f['found_by'])})" for f in flags)
        expected = downgrade_recommendation(final.recommendation_without_critical_findings)
        if LEVELS.index(recommendation) > LEVELS.index(expected):
            issues.append(f"Правило критичних знахідок ({who}): без знахідок модель дала б "
                          f"«{final.recommendation_without_critical_findings}», з ними має бути "
                          f"не вище «{expected}»; модель дала «{recommendation}» — знижено кодом.")
            recommendation = expected
            rule_by = "code"
        else:
            rule_by = "model"
            issues.append(f"Правило критичних знахідок ({who}): без знахідок модель дала б "
                          f"«{final.recommendation_without_critical_findings}», з ними — "
                          f"«{recommendation}» (правило виконано моделлю).")

    print("5/5 Збираю джерела та зберігаю...")
    used = {}
    all_stmts = ([s for sec in sections.values() for s in sec["statements"]]
                 + rationale + capital_stmts)
    for s in all_stmts:
        for cid in s["claim_ids"]:
            used.setdefault(claim_map[cid]["evidence_id"], set()).add(cid)
        for eid in s.get("evidence_ids", []):
            used.setdefault(eid, set())
    for c in conflicts:
        for cid in c["supporting"] + c["contradicting"]:
            used.setdefault(claim_map[cid]["evidence_id"], set()).add(cid)
    sources = []
    for eid, cids in sorted(used.items()):
        rec = evidence[eid]
        sources.append({
            "evidence_id": eid, "source_type": rec.get("source_type"),
            "title": rec.get("title"), "url": rec.get("url"),
            "claim_ids": sorted(cids),
        })

    report = {
        "drug": args.drug, "indication": args.indication,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "recommendation": recommendation,
        "recommendation_by_model": model_recommendation,
        "critical_rule_applied_by": rule_by,
        "red_flags": flags,
        "severity_triage": triage,
        "recommendation_rationale": rationale,
        "sections": sections,
        "capital_to_next_milestone": capital_stmts,
        "capital_calc": capital_calc,
        "conflicts": conflicts,
        "critical_unknowns": final.critical_unknowns,
        "diligence_questions": final.diligence_questions,
        "what_would_change_the_conclusion": final.what_would_change_the_conclusion,
        "sources": sources,
        "claims": claims,
        "issues": issues,
        "cost": {"calls": runner.calls, "input_tokens": runner.total_in,
                 "output_tokens": runner.total_out,
                 "usd": round(runner.total_cost, 6)},
    }

    out_json = RESULTS / f"{args.out_prefix}.json"
    out_md = RESULTS / f"{args.out_prefix}.md"
    out_claims = RESULTS / f"{args.out_prefix}_claims.md"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(render_md(report, out_claims.name))
    with open(out_claims, "w", encoding="utf-8") as f:
        f.write(render_claims_md(report))

    print(f"\nГотово: {out_json.name}, {out_md.name}, {out_claims.name}")
    print(f"Рекомендація: {recommendation}")
    print(f"Викликів: {runner.calls}, токени: {runner.total_in} вхід / "
          f"{runner.total_out} вихід, ~${runner.total_cost:.4f}")
    if issues:
        print(f"Автоматичні перевірки знайшли зауважень: {len(issues)} "
              f"(див. кінець {out_md.name})")

    if args.compare:
        old = load_json(Path(args.compare))
        print("\nПОРІВНЯННЯ З ПОПЕРЕДНІМ ЗВІТОМ")
        print(f"  Було: {old['recommendation']}  ->  Стало: {recommendation}")
        if flags:
            print("  Критичні знахідки: " + "; ".join(f"{f['id']} ({f['kind']})" for f in flags))
        new_ids = [c["id"] for c in claims if c.get("is_extra")]
        print(f"  Нові claims: {', '.join(new_ids) or 'немає'}")
        old_unknowns = set(old.get("critical_unknowns", []))
        for u in final.critical_unknowns:
            if u not in old_unknowns:
                print(f"  + нове критичне невідоме: {u}")

if __name__ == "__main__":
    main()