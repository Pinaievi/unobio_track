"""Календар катализаторів і PoS (імовірність успіху за опублікованими еталонами).

Все рахує КОД з реєстру (ClinicalTrials.gov / AACT) і з таблиці еталонних ставок. LLM тут не
бере участі. Календар показує, коли очікуються дані: це дати з реєстру, не прогноз.
PoS — ДОПУЩЕННЯ: середня частка програм, що пройшли етап, а не оцінка конкретного активу.
"""
import json
import re
from datetime import date

from text_utils import find_key, norm_status, norm_int
from capital import parse_date, cost_for_indication

# ---------------------------------------------------------------- еталонні ставки

BENCH_SOURCE = ("BIO, Informa Pharma Intelligence, QLS: Clinical Development Success Rates "
                "and Contributing Factors 2011-2020 (2021), "
                "https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf")

# частка програм, що перейшли на наступний етап (Phase I->II, II->III, III->NDA/BLA, NDA->схвалення)
BENCH = {
    "All indications": {"p1": 0.520, "p2": 0.289, "p3": 0.578, "nda": 0.906, "loa": 0.079},
    "Metabolic":       {"p1": 0.618, "p2": 0.450, "p3": 0.636, "nda": 0.875, "loa": 0.155},
}
# яка еталонна група підходить до терапевтичної області з core/capital.py
AREA_TO_BENCH = {"cardiometabolic": "Metabolic"}

PHASE_RE = re.compile(r"PHASE\s*([1-4])", re.I)
NCT_RE = re.compile(r"NCT\d{8}")


# ---------------------------------------------------------------- випробування препарату

def _phases(meta: dict) -> set:
    raw = find_key(meta, ["phases", "phase"])
    txt = json.dumps(raw) if raw is not None else ""
    return {int(m) for m in PHASE_RE.findall(txt)}


def target_trials(evidence: dict, indication_words: set) -> list:
    """Випробування цільового препарату з записів nct / nct_aact, дублі зливаємо за NCT.
    Фаза, статус, дати, спонсор беруться з реєстру."""
    table = {}
    recs = [r for r in evidence.values() if r.get("source_type") in ("nct", "nct_aact")]
    recs.sort(key=lambda r: r.get("source_type") != "nct_aact")
    for r in recs:
        m = NCT_RE.search(" ".join(str(r.get(k) or "") for k in ("id", "url", "title")))
        if not m:
            continue
        meta = r.get("meta") or {}
        t = table.setdefault(m.group(0), {
            "nct": m.group(0), "evidence_ids": [], "title": None, "status": "",
            "phases": set(), "enrollment": None, "start": None,
            "primary_completion": None, "completion": None, "sponsor": None,
            "conditions": [], "primary_outcome": None, "has_results": None,
            "why_stopped": None, "url": r.get("url")})
        t["evidence_ids"].append(r["id"])
        t["title"] = t["title"] or r.get("title") or meta.get("brief_title")
        t["url"] = t["url"] or r.get("url")
        t["status"] = t["status"] or norm_status(meta.get("status"))
        t["phases"] |= _phases(meta)
        if t["enrollment"] is None:
            t["enrollment"] = norm_int(meta.get("enrollment"))
        t["start"] = t["start"] or parse_date(meta.get("start_date"))
        t["primary_completion"] = t["primary_completion"] or parse_date(
            meta.get("primary_completion") or meta.get("primary_completion_date"))
        t["completion"] = t["completion"] or parse_date(
            meta.get("completion") or meta.get("completion_date"))
        sp = meta.get("lead_sponsor")
        t["sponsor"] = t["sponsor"] or (sp.get("name") if isinstance(sp, dict) else sp)
        if not t["conditions"]:
            t["conditions"] = list(meta.get("conditions") or [])
        outs = meta.get("primary_outcomes") or []
        if not t["primary_outcome"] and outs:
            t["primary_outcome"] = outs[0] if isinstance(outs[0], str) else json.dumps(outs[0])
        if t["has_results"] is None and meta.get("has_results") is not None:
            t["has_results"] = bool(meta.get("has_results"))
        t["why_stopped"] = t["why_stopped"] or meta.get("why_stopped")
    for t in table.values():
        blob = (" ".join(t["conditions"]) + " " + (t["title"] or "")).lower()
        t["in_indication"] = (not indication_words) or any(w in blob for w in indication_words)
    return sorted(table.values(), key=lambda t: t["nct"])


# ---------------------------------------------------------------- календар катализаторів

def phase_label(phases: set) -> str:
    return "/".join(f"Phase {p}" for p in sorted(phases)) if phases else "phase not stated"


def catalyst_calendar(evidence: dict, indication_words: set, reported: set | None = None,
                      today: date | None = None) -> dict:
    """Дати очікуваних даних. Для кожного випробування препарату — первинне завершення
    (отримання основних даних). Для конкурентів — найраніше й найпізніше первинне
    завершення за препаратом. Дати без позначки «actual/estimated» у наших даних
    розрізняємо за положенням щодо сьогодні."""
    today = today or date.today()
    reported = reported or set()
    trials = target_trials(evidence, indication_words)
    rows = []
    for t in trials:
        pc = t["primary_completion"]
        stopped = t["status"] in ("TERMINATED", "WITHDRAWN", "SUSPENDED")
        if not pc and not stopped:
            continue
        # давні події показуємо лише для Phase 2+ у цьому показанні; Phase 1 і інші показання
        # з минулого — шум для інвестора (майбутні дати лишаємо всі)
        if pc and pc < today and not stopped and not (
                t["in_indication"] and max(t["phases"], default=0) >= 2):
            continue
        if stopped:
            kind = f"Programme event: trial {t['status'].lower()}"
        elif pc >= today:
            kind = "Expected primary data (primary completion)"
        elif t["has_results"]:
            kind = "Primary completion passed, results posted in the registry"
        elif t["nct"] in reported:
            kind = "Primary completion passed, results reported in the literature"
        else:
            kind = "Primary completion passed, no results in our sources yet"
        rows.append({
            "date": str(pc) if pc else "", "scope": "target", "kind": kind,
            "pivotal": 3 in t["phases"], "nct": t["nct"], "phase": phase_label(t["phases"]),
            "status": t["status"], "sponsor": t["sponsor"], "enrollment": t["enrollment"],
            "conditions": t["conditions"][:3], "primary_outcome": t["primary_outcome"],
            "in_indication": t["in_indication"], "past": bool(pc and pc < today),
            "note": t["why_stopped"] or "", "evidence_ids": t["evidence_ids"], "url": t["url"]})
    for r in evidence.values():
        if r.get("source_type") != "competitor_registry":
            continue
        m = r.get("meta") or {}
        pcs = [m.get("primary_completion_earliest"), m.get("primary_completion_latest")]
        pcs = [parse_date(x) for x in pcs if x]
        if not pcs:
            continue
        for d, label in sorted({(pcs[0], "earliest"), (pcs[-1], "latest")}):
            if d < today:           # минулі дати конкурентів — шум; лишаємо лише майбутні
                continue
            rows.append({
                "date": str(d), "scope": "competitor",
                "kind": f"Competitor Phase 3 programme: {label} primary completion",
                "pivotal": True, "nct": "", "phase": "Phase 3",
                "status": "; ".join(f"{k} {v}" for k, v in (m.get("statuses") or {}).items())
                if isinstance(m.get("statuses"), dict) else str(m.get("statuses") or ""),
                "sponsor": "; ".join(m.get("sponsors") or []), "enrollment": m.get("enrollment_total"),
                "conditions": [], "primary_outcome": f"{m.get('drug')} ({m.get('trials')} trials)",
                "in_indication": True, "past": d < today, "note": "",
                "evidence_ids": [r["id"]], "url": r.get("url")})
    rows.sort(key=lambda x: (x["date"] == "", x["date"]))
    upcoming = [x for x in rows if not x["past"] and x["scope"] == "target"]
    # «наступний катализатор» — з показання інвестиції; інші показання лише якщо інших немає
    own = [x for x in upcoming if x.get("in_indication", True)]
    return {"as_of": str(today), "rows": rows,
            "next_target_readout": (own or upcoming or [None])[0]}


# ---------------------------------------------------------------- PoS за еталоном

def catalysts_for_prompt(cal: dict, limit: int = 6) -> str:
    """Найближчі дати з реєстру для фінального виклику: тільки те, що є в календарі."""
    rows = [r for r in cal["rows"] if not r["past"]]
    mine = [r for r in rows if r["scope"] == "target" and r.get("in_indication", True)][:limit]
    comp = [r for r in rows if r["scope"] == "competitor"][:3]
    lines = [f"- {r['date']}: {r['nct']} ({r['phase']}, {r['status']}), primary endpoint: "
             f"{(r['primary_outcome'] or 'not stated')[:100]}" for r in mine]
    lines += [f"- {r['date']}: competitor programme {r['primary_outcome']}" for r in comp]
    return "\n".join(lines) or "none in the registry records"


def pos_benchmark(evidence: dict, indication_words: set, indication: str,
                  flags: list | None = None, reported: set | None = None) -> dict:
    """Поточний етап = найвища фаза серед випробувань препарату в цьому показанні.
    PoS до схвалення = добуток еталонних ставок від цього етапу. Це допущення з опублікованого
    еталону; код не коригує його під конкретний актив і лише позначає, коли є критичні знахідки."""
    trials = [t for t in target_trials(evidence, indication_words) if t["in_indication"]] \
        or target_trials(evidence, indication_words)
    phases = set().union(*[t["phases"] for t in trials]) if trials else set()
    if 4 in phases:
        stage = "approved_or_phase4"
    elif 3 in phases:
        stage = "phase3"
    elif 2 in phases:
        stage = "phase2"
    elif 1 in phases:
        stage = "phase1"
    else:
        stage = "unknown"
    area = cost_for_indication(indication)[0]
    groups = ["All indications"]
    if AREA_TO_BENCH.get(area):
        groups.append(AREA_TO_BENCH[area])
    path = {"phase1": ["p1", "p2", "p3", "nda"], "phase2": ["p2", "p3", "nda"],
            "phase3": ["p3", "nda"], "approved_or_phase4": [], "unknown": []}[stage]
    rows = []
    for g in groups:
        b = BENCH[g]
        p = 1.0
        for k in path:
            p *= b[k]
        rows.append({"benchmark": g,
                     "stage_rates": {k: b[k] for k in ("p1", "p2", "p3", "nda")},
                     "pos_to_approval": p if path else None,
                     "if_pivotal_phase3_positive": b["nda"] if stage == "phase3" else None})
    p3 = [t for t in trials if 3 in t["phases"]]
    return {
        "stage": stage, "area": area,
        "phase3_trials": [t["nct"] for t in p3],
        "phase3_with_results": [t["nct"] for t in p3 if t["has_results"] or t["nct"] in (reported or set())],
        "evidence_ids": sorted({e for t in trials for e in t["evidence_ids"]}),
        "rows": rows, "source": BENCH_SOURCE,
        "critical_findings": [f["id"] for f in (flags or [])],
    }


def outlook_statements(cal: dict, pos: dict) -> tuple:
    """Тексти для розділів звіту: (календар, PoS). Усі — висновки коду з реєстру й еталону."""
    cal_stmts = []
    target = [r for r in cal["rows"] if r["scope"] == "target"]
    comp = [r for r in cal["rows"] if r["scope"] == "competitor"]
    nxt = cal.get("next_target_readout")
    if nxt:
        cal_stmts.append({
            "text": f"Next expected data from the registry: {nxt['nct']} ({nxt['phase']}, "
                    f"{nxt['status']}) primary completion {nxt['date']}"
                    + (f"; primary endpoint: {nxt['primary_outcome']}" if nxt['primary_outcome'] else "")
                    + ". Dates come from the registry and can move.",
            "kind": "evidence", "claim_ids": [], "evidence_ids": nxt["evidence_ids"],
            "unverified_numbers": []})
    else:
        cal_stmts.append({
            "text": "No upcoming primary-completion date for this drug was found in the "
                    "retrieved registry records.",
            "kind": "inference", "claim_ids": [], "evidence_ids": [], "unverified_numbers": []})
    passed = [r for r in target if r["past"] and "no results" in r["kind"] and r["in_indication"]]
    if passed:
        cal_stmts.append({
            "text": "Primary completion has passed but no results are in our sources for: "
                    + ", ".join(r["nct"] for r in passed)
                    + ". Either results exist outside our sources (for example a conference "
                      "or a press release) or the readout is late; this is a diligence question.",
            "kind": "inference", "claim_ids": [], "evidence_ids":
                [e for r in passed for e in r["evidence_ids"]], "unverified_numbers": []})
    if comp:
        cal_stmts.append({
            "text": "Competitor Phase 3 programmes with registry dates are listed in the table "
                    "below; they show when the competitive picture may change, not whose "
                    "drug is better.",
            "kind": "inference", "claim_ids": [], "evidence_ids": [], "unverified_numbers": []})
    cal_stmts.append({
        "text": "Not predicted: regulatory filing and approval dates, and results of trials "
                "that are not in the registry. Registry dates are the sponsor's own estimates.",
        "kind": "inference", "claim_ids": [], "evidence_ids": [], "unverified_numbers": []})

    pos_stmts = []
    stage_name = {"phase1": "Phase 1", "phase2": "Phase 2", "phase3": "Phase 3",
                  "approved_or_phase4": "Phase 4 / approved", "unknown": "unknown"}[pos["stage"]]
    if pos["stage"] in ("unknown", "approved_or_phase4"):
        pos_stmts.append({
            "text": f"PoS benchmark not computed: the highest phase in the registry records is "
                    f"{stage_name}.",
            "kind": "inference", "claim_ids": [], "evidence_ids": pos["evidence_ids"],
            "unverified_numbers": []})
    else:
        for r in pos["rows"]:
            s = (f"ASSUMPTION from a published benchmark ({r['benchmark']}), not from the "
                 f"drug's own data: the highest phase in the registry is {stage_name}, and the "
                 f"average programme at this stage reaches approval about "
                 f"{r['pos_to_approval'] * 100:.0f}% of the time.")
            if r["if_pivotal_phase3_positive"]:
                s += (f" If the pivotal Phase 3 is positive the benchmark for approval rises to "
                      f"about {r['if_pivotal_phase3_positive'] * 100:.0f}% (NDA/BLA to approval); "
                      f"if it fails the programme stops.")
            pos_stmts.append({"text": s, "kind": "inference", "claim_ids": [],
                              "evidence_ids": pos["evidence_ids"], "unverified_numbers": []})
        if pos["phase3_with_results"]:
            pos_stmts.append({
                "text": "Phase 3 results already reported (registry or literature) for: "
                        + ", ".join(pos["phase3_with_results"])
                        + ". The benchmark does not know them: read the efficacy and safety "
                          "sections to judge whether this asset is above or below the average.",
                "kind": "inference", "claim_ids": [], "evidence_ids": pos["evidence_ids"],
                "unverified_numbers": []})
        note = ("The benchmark is an average over many programmes and is not adjusted for "
                "this asset's data, class or sponsor; the asset-specific evidence is in the "
                "other sections.")
        if pos["critical_findings"]:
            note += (" Critical findings are present (" + ", ".join(pos["critical_findings"])
                     + "): treat the benchmark as an upper bound.")
        pos_stmts.append({"text": note, "kind": "inference", "claim_ids": [],
                          "evidence_ids": [], "unverified_numbers": []})
    return cal_stmts, pos_stmts