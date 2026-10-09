import json
import re

from datetime import date, datetime
from core.config import * 
from core.text_utils import *

AREA_COSTS = {
    "oncology": (40_000, 120_000,
                 ["cancer", "carcinoma", "tumor", "tumour", "lymphoma", "leukemia",
                  "myeloma", "nsclc", "neoplasm", "sarcoma", "melanoma"]),
    "neurology": (25_000, 80_000,
                  ["alzheimer", "parkinson", "multiple sclerosis", "epilep", "dementia",
                   "als", "huntington", "migraine"]),
    "immunology": (20_000, 60_000,
                   ["psoriasis", "arthritis", "colitis", "crohn", "asthma", "copd",
                    "lupus", "dermatitis", "hidradenitis", "inflammatory", "airway"]),
    "rare": (50_000, 200_000,
             ["angioedema", "rare", "orphan", "dystrophy", "fibrosis imperfecta"]),
    "cardiometabolic": (15_000, 50_000,
                        ["obesity", "diabet", "hypertension", "lipoprotein", "cholesterol",
                         "cardiovascular", "heart", "nash", "mash", "steatohepatitis",
                         "weight"]),
}
DEFAULT_COST = ("general", 15_000, 50_000)

ENROLLING = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}
REMAINING_FLOOR = 0.10

def parse_date(v):
    """Дата з реєстру ('2025-05-01', '2025-05', {'date': ...}) -> date або None."""
    if isinstance(v, dict):
        v = v.get("date")
    if not v:
        return None
    txt = str(v).strip()[:10]
    for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7)):
        try:
            return datetime.strptime(txt[:n], fmt).date()
        except ValueError:
            continue
    return None

def months_between(a, b) -> float:
    return (b - a).days / 30.4

def cost_for_indication(indication: str):
    """Повертає (область, мін, макс) USD на учасника за ключовими словами показання."""
    t = (indication or "").lower()
    for area, (lo, hi, words) in AREA_COSTS.items():
        for w in words:
            if (len(w) <= 4 and re.search(rf"\b{re.escape(w)}\b", t)) or \
                    (len(w) > 4 and w in t):
                return area, lo, hi
    return DEFAULT_COST

def capital_from_registry(evidence: dict, claims: list, claim_map: dict,
                          issues: list, drug: str, indication: str):
    """Капітал до наступної віхи — ДЕТЕРМІНОВАНО, за статусом у реєстрі:
      - рахуємо Phase 3, що набирають учасників (RECRUITING / NOT_YET_RECRUITING /
        ENROLLING_BY_INVITATION) і ще без результатів;
      - набір закрито (ACTIVE_NOT_RECRUITING), завершені, із результатами чи
        опубліковані в літературі — не рахуємо, лише перелічуємо;
      - розмір вибірки — з реєстру; суму і вартість рахує код."""
    area, cost_lo, cost_hi = cost_for_indication(indication)
    if area == "general":
        issues.append("Capital: терапевтичну область не визначено за показанням — "
                      "використано загальний діапазон допущення")
    table = trial_table(evidence)
    reported = reported_trials(claims, evidence)
    counted, closed, done = [], [], []
    other = [] 
    for nct, t in sorted(table.items()):
        if not t["phase3"]:
            if t["phase3"] is None:
                issues.append(f"Capital: {nct} пропущено — фаза в реєстрі не вказана")
            continue
        if t["has_results"] or nct in reported or t["status"] in (
                "COMPLETED", "TERMINATED", "WITHDRAWN"):
            done.append(t)
        elif t["status"] == "ACTIVE_NOT_RECRUITING":
            closed.append(t)
        elif t["status"] in ENROLLING:
            if t["enrollment"] is None:
                issues.append(f"Capital: {nct} набирає учасників, але розмір вибірки "
                              f"у реєстрі не вказано — не пораховано")
                continue
            counted.append(t)
        else:
            issues.append(f"Capital: {nct} має статус «{t['status'] or '?'}» — "
                          f"не пораховано")

    def claim_ids_of(t):
        return [c["id"] for c in claims if c["evidence_id"] in t["evidence_ids"]][:3]

    def short(t):
        return (t["title"] or t["nct"])[:90]

    if done:
        milestone = "regulatory submission (some Phase 3 trials have already finished"\
                    " or reported)"
    else:
        milestone = "completion of the Phase 3 programme"
    if counted:
        milestone += "; remaining capital goes to Phase 3 trials that are still enrolling"
    else:
        milestone += ("; no Phase 3 trial is enrolling any more, so remaining spend is "
                      "follow-up and data readout of trials with closed enrollment, "
                      "plus the filing")
    stmts = [{"text": f"Next milestone (AI inference from registry status): "
                      f"{milestone}.",
              "kind": "inference", "claim_ids": [],
              "evidence_ids": sorted({e for t in done + counted for e in
                                      t["evidence_ids"]}),
              "unverified_numbers": []}]
    today = date.today()
    active = counted + closed 
    sponsors = sorted({t["sponsor"] for t in active + done if t.get("sponsor")})
    if sponsors:
        stmts.append({
            "text": "Lead sponsor(s) of the Phase 3 trials according to the registry: "
                    + "; ".join(sponsors) + ".",
            "kind": "evidence", "claim_ids": [],
            "evidence_ids": [e for t in active + done for e in t["evidence_ids"]],
            "unverified_numbers": []})
    for t in active:
        state = ("still enrolling" if t in counted else "enrollment closed")
        dates = (f", start {t['start']}" if t.get("start") else "") + \
                (f", primary completion {t['primary_completion']}"
                 if t.get("primary_completion") else "")
        stmts.append({
            "text": f"{t['nct']} ({short(t)}): Phase 3, registry status "
                    f"{t['status']} ({state}), "
                    f"{(t['enrollment'] or 0):,} participants planned{dates}.",
            "kind": "evidence", "claim_ids": claim_ids_of(t),
            "evidence_ids": t["evidence_ids"], "unverified_numbers": []})
    if done:
        stmts.append({
            "text": "Phase 3 trials excluded because they are completed or have "
                    "results: " + ", ".join(t["nct"] for t in done) + ".",
            "kind": "evidence", "claim_ids": [],
            "evidence_ids": [e for t in done for e in t["evidence_ids"]],
            "unverified_numbers": []})
    if other:
        stmts.append({
            "text": f"Phase 3 trials in other indications are not counted: "
                    + ", ".join(t["nct"] for t in other) + ".",
            "kind": "evidence", "claim_ids": [],
            "evidence_ids": [e for t in other for e in t["evidence_ids"]],
            "unverified_numbers": []})
        
    rows = []
    for t in active:
        if not t["enrollment"]:
            issues.append(f"Capital: {t['nct']} без розміру вибірки — не пораховано")
            continue
        f_lo, f_hi, why = remaining_fraction(t, today)
        tot_lo, tot_hi = t["enrollment"] * cost_lo, t["enrollment"] * cost_hi
        rows.append({"nct": t["nct"], "participants": t["enrollment"],
                     "status": t["status"], "start": str(t.get("start") or ""),
                     "primary_completion": str(t.get("primary_completion") or ""),
                     "remaining_fraction": [f_lo, f_hi], "why": why,
                     "total_usd": [tot_lo, tot_hi],
                     "remaining_usd": [tot_lo * f_lo, tot_hi * f_hi]})
    calc = None
    if rows:
        dated = [r for r in rows if not r["why"].startswith("dates missing")]
        undated = [r for r in rows if r["why"].startswith("dates missing")]
        low = sum(r["remaining_usd"][0] for r in rows)
        high = sum(r["remaining_usd"][1] for r in rows)
        d_low = sum(r["remaining_usd"][0] for r in dated)
        d_high = sum(r["remaining_usd"][1] for r in dated)
        pcs = sorted(t["primary_completion"] for t in active
                     if t.get("primary_completion"))
        calc = {"participants_total": sum(r["participants"] for r in rows),
                "cost_area": area,
                "cost_per_participant_low": cost_lo,
                "cost_per_participant_high": cost_hi,
                "trials": rows, "usd_low": low, "usd_high": high,
                "trials_counted": [t["nct"] for t in counted],
                "trials_enrollment_closed": [t["nct"] for t in closed],
                "trials_excluded_done": [t["nct"] for t in done]}
        def line(r):
            return (f"{r['nct']}: ${r['remaining_usd'][0] / 1e6:,.0f}M-"
                    f"${r['remaining_usd'][1] / 1e6:,.0f}M ({r['why']})")
        text = (f"AI inference with an ASSUMPTION that is not from the sources "
                f"(cost range for the area '{area}', spend spread evenly between "
                f"start and primary completion, at least "
                f"{REMAINING_FLOOR * 100:.0f}% always left). Trials with known dates: "
                + ("; ".join(line(r) for r in dated) or "none")
                + f". Subtotal about ${d_low / 1e6:,.0f}M-${d_high / 1e6:,.0f}M.")
        if undated:
            text += (" Trials WITHOUT a primary completion date in the registry data "
                     "(the range is wide because progress is unknown): "
                     + "; ".join(line(r) for r in undated)
                     + f". Together with them the total is about "
                       f"${low / 1e6:,.0f}M-${high / 1e6:,.0f}M.")
        text += " Excludes manufacturing, regulatory filing and launch."
        calc["dated_usd"] = [d_low, d_high]
        stmts.append({
            "text": text,
            "kind": "inference",
            "claim_ids": sorted({i for t in active for i in claim_ids_of(t)}),
            "evidence_ids": [e for t in active for e in t["evidence_ids"]],
            "unverified_numbers": []})
        if pcs:
            first, last = pcs[0], pcs[-1]
            m_first = months_between(today, first)
            m_last = months_between(today, last)
            def when(m, d):
                return (f"{abs(m):.0f} months ago ({d})" if m < 0
                        else f"in about {m:.0f} months ({d})")
            text = (f"AI inference from registry dates: the earliest planned primary "
                    f"completion of these Phase 3 trials is {when(m_first, first)}"
                    + (f", the latest {when(m_last, last)}" if last != first else "")
                    + ". Primary completion is not the same as results being "
                      "published.")
            stmts.append({"text": text, "kind": "inference", "claim_ids": [],
                          "evidence_ids": [e for t in active for e in
                                           t["evidence_ids"]],
                          "unverified_numbers": []})
            if m_last > 0 and high > 0:
                calc["months_to_last_primary_completion"] = round(m_last, 1)
                calc["monthly_burn_usd"] = [low / max(m_last, 1),
                                            high / max(m_last, 1)]
    else:
        stmts.append({"text": "No Phase 3 trial with a known size is in progress, so "
                              "the remaining trial spend cannot be computed from the "
                              "registry (it has no cost or progress data).",
                      "kind": "inference", "claim_ids": [], "evidence_ids": [],
                      "unverified_numbers": []})
    stmts += funding_statements(evidence, calc, issues)
    for note in ("Trial status and enrollment are a snapshot of the registry at "
                 "the time of the search.",
                 "Cost per participant is an assumed range for the therapeutic area "
                 "(not from the sources); the share of cost already spent is "
                 "estimated from elapsed time, not from real progress; real costs "
                 "differ by trial design, country and duration."):
        stmts.append({"text": f"Limit of the estimate: {note}", "kind": "inference",
                      "claim_ids": [], "evidence_ids": [], "unverified_numbers": []})
    return stmts, calc

def funding_statements(evidence: dict, calc, issues: list) -> list:
    """Фінансування спонсора з SEC EDGAR: цифри беремо з meta запису, порівняння
    рахує код. Це загальні цифри компанії, не витрати на цей препарат."""
    recs = [r for r in evidence.values() if r.get("source_type") == "sec_filings"]
    if not recs:
        return [{"text": "Sponsor funding: the lead sponsor of the trials is not an SEC "
                         "filer (it may be private or foreign), so cash and runway "
                         "could not be compared with the estimated need.",
                 "kind": "inference", "claim_ids": [], "evidence_ids": [],
                 "unverified_numbers": []}]
    out = []
    for r in recs:
        m = r.get("meta") or {}
        who = f"{m.get('company')} ({m.get('ticker') or 'no ticker'})"
        if not m.get("sponsor_verified"):
            out.append({"text": f"Sponsor funding: {who} was found only by a text search "
                                f"for the drug name in SEC filings; it may be a "
                                f"competitor or a royalty holder, so its figures are "
                                f"NOT used. Identify the real sponsor first.",
                        "kind": "inference", "claim_ids": [], "evidence_ids": [r["id"]],
                        "unverified_numbers": []})
            continue

        def money(v, unit):
            return f"${v:,.0f}" if unit == "USD" else f"{unit} {v:,.0f}"

        parts = []
        if m.get("cash_value") is not None:
            parts.append(f"cash and cash equivalents "
                         f"{money(m['cash_value'], m.get('cash_unit'))} as of "
                         f"{m['cash_date']}")
        if m.get("rd_value") is not None:
            parts.append(f"R&D expense {money(m['rd_value'], m.get('rd_unit'))} for the "
                         f"fiscal year ended {m['rd_fy_end']}")
        if m.get("opcf_value") is not None:
            parts.append(f"net operating cash flow "
                         f"{money(m['opcf_value'], m.get('opcf_unit'))} for the fiscal "
                         f"year ended {m['opcf_fy_end']}")
        out.append({"text": f"Sponsor funding (SEC EDGAR, company-wide, not specific to "
                            f"this drug) for {who}"
                            + (f" [{m['sponsor_source']}]" if m.get("sponsor_source")
                               else "") + ": " + "; ".join(parts) + ".",
                    "kind": "evidence", "claim_ids": [], "evidence_ids": [r["id"]],
                    "unverified_numbers": []})
        if m.get("cash_unit") != "USD" or m.get("opcf_unit") != "USD":
            issues.append(f"Capital: цифри {m.get('company')} не в USD — порівняння не "
                          f"робилось")
            continue
        cash, opcf = m.get("cash_value"), m.get("opcf_value")
        bits = []
        if cash is not None and opcf is not None and opcf < 0:
            bits.append(f"at the last annual cash burn the cash lasts about "
                        f"{cash / -opcf * 12:,.0f} months")
        if cash and calc and calc.get("usd_high"):
            lo, hi = calc["usd_low"], calc["usd_high"]
            bits.append(f"the assumed cost of the counted Phase 3 trials "
                        f"(${lo / 1e6:,.0f}M-${hi / 1e6:,.0f}M) is "
                        f"{lo / cash * 100:,.0f}%-{hi / cash * 100:,.0f}% of the "
                        f"current cash")
        if bits:
            out.append({"text": "AI inference from the company-wide figures above "
                                "(ignores other programmes, debt and future "
                                "financing): " + "; ".join(bits) + ".",
                        "kind": "inference", "claim_ids": [], "evidence_ids": [r["id"]],
                        "unverified_numbers": []})
    return out

def trial_table(evidence: dict) -> dict:
    """Збираємо випробування з основних записів реєстру (nct, nct_aact), зливаючи
    дублі за NCT-номером. Фаза, статус і розмір вибірки беруться з реєстру, а не з
    тексту моделі."""
    recs = [r for r in evidence.values()
            if r.get("source_type") in ("nct", "nct_aact")]
    recs.sort(key=lambda r: r.get("source_type") != "nct_aact")
    table = {}
    for r in recs:
        m = re.search(r"NCT\d{8}", " ".join(str(r.get(k) or "")
                                            for k in ("id", "url", "title")))
        if not m:
            continue
        t = table.setdefault(m.group(0), {
            "nct": m.group(0), "evidence_ids": [], "title": None, "status": "",
            "phase3": None, "enrollment": None, "has_results": None, "blob": "",
            "start": None, "primary_completion": None, "sponsor": None})
        meta = r.get("meta") or {}
        t["evidence_ids"].append(r["id"])
        t["title"] = t["title"] or r.get("title")
        t["blob"] += " " + json.dumps(r, ensure_ascii=False).lower()
        if not t["status"]:
            t["status"] = norm_status(find_key(meta, ["status", "overall_status",
                                                      "overallStatus"]))
        ph = find_key(meta, ["phase", "phases"])
        if t["phase3"] is None and ph:
            t["phase3"] = norm_phase3(ph)
        if t["enrollment"] is None:
            t["enrollment"] = norm_int(find_key(meta, ["enrollment",
                                                       "enrollment_count",
                                                       "enrollmentInfo"]))
        if t["start"] is None:
            t["start"] = parse_date(find_key(
                meta, ["start_date", "startDateStruct", "startDate",
                       "start_date_struct"]))
        if t["primary_completion"] is None:
            t["primary_completion"] = parse_date(find_key(
                meta, ["primary_completion", "primary_completion_date",
                       "primaryCompletionDateStruct", "primaryCompletionDate",
                       "primary_completion_date_struct", "completion",
                       "completion_date", "completionDateStruct", "completionDate"]))
        if not t["sponsor"]:
            sp = find_key(meta, ["lead_sponsor", "leadSponsor"])
            if isinstance(sp, dict):
                sp = sp.get("name")
            t["sponsor"] = str(sp) if sp else None
        hr = find_key(meta, ["has_results", "hasResults"])
        if t["has_results"] is None and hr is not None:
            t["has_results"] = str(hr).lower() in ("true", "1", "yes")
    return table

def remaining_fraction(t: dict, today):
    """Яка частка вартості Phase 3 ще попереду. Припущення: витрати розподілені рівномірно
    між стартом і первинним завершенням. Повертає (мін, макс, пояснення)."""
    st, pc = t.get("start"), t.get("primary_completion")
    if t["status"] == "NOT_YET_RECRUITING" or (st and st > today):
        return 1.0, 1.0, "not started yet"
    if st and pc and pc > st:
        elapsed = min(max((today - st).days / (pc - st).days, 0.0), 1.0)
        f = max(1.0 - elapsed, REMAINING_FLOOR)
        return f, f, f"{elapsed * 100:.0f}% of planned time elapsed"
    return REMAINING_FLOOR, 1.0, "dates missing: range 10%-100%"

def reported_trials(claims: list, evidence: dict) -> set:
    """NCT-номери випробувань, результати яких уже є в літературі: стаття (не реєстр)
    згадує NCT і дає claim із напрямком supports/contradicts. Такі випробування
    не потребують капіталу до наступної віхи."""
    out = set()
    for c in claims:
        if c["source_type"] in ("pubmed", "epmc_pmc", "epmc_ppr") \
                and c["direction"] in ("supports", "contradicts"):
            rec = evidence.get(c["evidence_id"], {})
            blob = (rec.get("text") or "") + " " + (rec.get("title") or "")
            out |= set(re.findall(r"NCT\d{8}", blob))
    return out