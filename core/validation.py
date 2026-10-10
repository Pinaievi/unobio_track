import re
from typing import Literal
from pydantic import BaseModel, Field
from core.text_utils import *
from core.config import *

class Conflict(BaseModel):
    topic: str = Field(description="What the disagreement is about, one line.")
    endpoint: str = Field(
        description="The ONE outcome that both sides measure (for example "
                    "'permanent discontinuation due to adverse events')."
    )
    shared_comparator: str = Field(
        description="The comparator that BOTH sides use: 'placebo', the name of an "
                    "active drug, or 'none stated'. Both sides must share it."
    )
    supporting_claim_ids: list[str]
    contradicting_claim_ids: list[str]
    assessment: str = Field(
        description="Your inference: which side is stronger and why (confidence, "
                    "source type, dose, population, certainty) or why it cannot be "
                    "decided. Do not write claim ids inside the text."
    )
    status: Literal["resolved", "unresolved"]

class ConflictsDraft(BaseModel):
    conflicts: list[Conflict]


PLACEBO_RE = re.compile(r"(?i)\bplacebo\b|control group|control arm|\bcontrols?\b")
ACTIVE_RE = re.compile(r"(?i)other (?:incretin|glp|treatment|therap|drug|agent)|"
                       r"tirzepatide|semaglutide|dulaglutide|liraglutide|"
                       r"active comparator|danuglipron")

RISK_ASSOC_RE = re.compile(r"(?i)hazard ratio|odds ratio|relative risk|(?-i:\bHR\b)|(?-i:\bOR\b)\s*[=:]?\s*\d")

INN_RE = re.compile(
    r"(?i)\b[a-z]{3,}(?:mab|tug|cept|tinib|rasib|parib|ciclib|stat|tide|glutide|"
    r"siran|gene|vir|tecan|degib|sertib|lisib|zomib)\b")

NOT_CONFLICT_RE = re.compile(
    r"(?i)not an? (?:true |real |direct |empirical )*(?:contradiction|conflict)|"
    r"matter of (?:clinical )?(?:judg|interpret)|mechanistic hypothesis|"
    r"not (?:really )?contradict")

NO_HUMAN_DATA_RES = [
    re.compile(r"(?i)\b(?:do(?:es)? not|did not|no|without|lack(?:s|ing)?|absence of)\b"
               r"[^.;]{0,80}\b(?:results? (?:from|of) (?:human )?clinical (?:trials?|studies)"
               r"|human (?:clinical )?(?:trials?|data|results|efficacy|evidence)"
               r"|clinical (?:trial|efficacy|outcome) (?:data|results))"),
    re.compile(r"(?i)clinical efficacy[^.;]{0,80}(?:preclinical|case report)"),
    re.compile(r"(?i)\bpreclinical\b[^.;]{0,40}\b(?:and|plus)\b[^.;]{0,20}\bcase report"),
]

RESOLVED_TEXT_RE = re.compile(
    r"(?i)\b(?:the )?(?:conflict|issue|dispute|question) (?:is|was|can be) "
    r"resolved[^.]*\.\s*")

RESOLVED_TEXT_RE = re.compile(
    r"(?i)\b(?:the )?(?:conflict|issue|dispute|question) (?:is|was|can be) "
    r"resolved[^.]*\.\s*")

CROSS_LINK_RE = re.compile(
    r"(?i)\bfrom\b[^.]{0,40}\d[^.]{0,20}\bto\b[^.]{0,20}\d|"
    r"\b(?:rose|rise[ns]?|risen|higher than|lower than|whereas|building on|"
    r"consistent with|confirm\w*)\b")

GAP_RE = re.compile(
    r"(?i)\b(?:no|not any|without any)\s+(?:published\s+|publicly\s+available\s+|"
    r"reported\s+|available\s+)*(?:clinical|human|efficacy|safety|trial|data)|"
    r"\b(?:lack|absence) of\b|\bno FDA[- ](?:approved|drug labels?|labels?)\b|"
    r"\bnot (?:yet )?(?:been )?(?:published|reported)\b|"
    r"\bcannot be (?:estimated|determined)\b|"
    r"\b(?:indicating|suggesting|implying)\b[^.]{0,80}\b(?:not|no)\b[^.]{0,40}\bapprov")

SOURCES_RE = re.compile(r"(?i)(?:retrieved|provided|available|reviewed|these|the) sources|"
                        r"in the (?:claims|dossier|records)|not covered by")

MECH_STAGES = {"mechanism", "translation"}

ID_LIST_RE = re.compile(r"\s*[\[(]\s*(?:(?:claims?\s+)?[CX]\d{3}\s*[,;]?\s*(?:and\s+)?)+[\])]")

def strip_inline_ids(text: str) -> str:
    """Номери claims мають бути лише в claim_ids. Прибираємо їх із вільного тексту:
    «[X002]» і «(C101, C102)» зникають, «claim C101» -> «a claim»."""
    t = ID_LIST_RE.sub("", text or "")
    t = re.sub(r"(?i)\b(?:claims?\s+)?[CX]\d{3}\b", "a claim", t)
    return re.sub(r"\s{2,}", " ", t).strip()

def validate_statements(statements: list, claim_map: dict, section: str, issues: list,
                        single_evidence: bool = False):
    """Прибираємо вигадані id, позначаємо числа без підтримки в claims.
    «evidence» знижуємо до «inference», якщо воно склеює різне:
      - claims з біології/PK (mechanism, translation) і з клініки разом;
      - claims із напрямками supports і contradicts разом;
      - (single_evidence) більше одного claim: у рекомендації факт = один claim."""
    out = []
    for s in statements:
        ids = [i for i in s.claim_ids if i in claim_map]
        bad = [i for i in s.claim_ids if i not in claim_map]
        if bad:
            issues.append(f"{section}: invented ids {bad} removed")
        item = {"text": strip_inline_ids(s.text), "kind": s.kind, "claim_ids": ids,
                "unverified_numbers": []}
        gap = GAP_RE.search(s.text)
        if gap and not SOURCES_RE.search(s.text):
            if gap.start() <= 12:
                item["text"] = ("In the retrieved sources: " + s.text[0].lower() + s.text[1:])

            if s.kind == "evidence":
                item["kind"] = "inference"
            issues.append(f"{section}: statement about missing data -> [AI]"
                          f"{' with a source note' if gap.start() <= 12 else ''}: "
                          f"{s.text[:70]}")
        if single_evidence and ids and item["kind"] == "evidence" \
                and all(claim_map[i]["stage"] in MECH_STAGES for i in ids):
            issues.append(f"{section}: trivial [E] about the mechanism removed from "
                          f"the recommendation (it is in section 1): {s.text[:70]}")
            continue
        if item["kind"] == "evidence":
            if not ids:
                issues.append(f"{section}: evidence without claims dropped: "
                              f"{s.text[:70]}")
                continue
            if section.startswith("Commercial") and all(
                    claim_map[i].get("source_type") == "nct_aact_population" for i in ids):
                
                issues.append(f"{section}: [E] based only on study inclusion criteria "
                              f"(not a market indicator) dropped: {s.text[:70]}")
                continue
            families = {claim_map[i]["stage"] in MECH_STAGES for i in ids}
            dirs = {claim_map[i]["direction"] for i in ids}
            reason = None
            if len(families) > 1:
                reason = "combines biology/PK and clinical data"
            elif {"supports", "contradicts"} <= dirs:
                reason = "combines claims with opposite directions"
            elif len({claim_map[i].get("evidence_id") for i in ids}) > 1 \
                    and CROSS_LINK_RE.search(s.text):
                reason = ("compares claims from different records (comparison/change "
                          "between sources — a model inference, not a fact)")
            elif any(claim_map[i].get("source_type") == "opentargets" for i in ids) \
                    and _ot_label_mismatch(s.text, ids, claim_map):
                reason = ("evidence type (genetic/clinical/literature) for the Open Targets score "
                          "is named, but the cited claims do not give such a score with these numbers")
            elif any(claim_map[i].get("confidence") == "low" for i in ids):
                reason = "cited claims include low-confidence ones: not presented as fact"
            elif section.startswith("Commercial") \
                    and len({claim_map[i].get("evidence_id") for i in ids}) > 1 \
                    and len(numbers(strip_labels(s.text))) >= 2:
                reason = ("in commercial, numbers from different records in one [E] "
                          "(they may be different measures)")
            elif section.startswith("Commercial") and (
                    RISK_ASSOC_RE.search(s.text)
                    or any(RISK_ASSOC_RE.search(claim_map[i]["claim"] + " " + claim_map[i]["quote"])
                           for i in ids)):
                reason = ("risk association (HR/OR) describes the disease, not the market size: "
                          "not presented as a fact about the commercial opportunity")
            elif single_evidence and len(ids) > 1:
                reason = "in the recommendation a fact must rest on a single claim"
            elif single_evidence and any(
                    claim_map[i].get("confidence") == "low"
                    or claim_map[i].get("source_type") == "epmc_ppr" for i in ids):
                reason = "in the recommendation low-confidence/preprint cannot be presented as fact"
            if not reason:

                no_ci = re.sub(r"(?i)\d+\s*%\s*(?:CI|confidence interval)", "", item["text"])
                have_pct = set()
                for i in ids:
                    have_pct |= percent_numbers(claim_map[i]["claim"]) \
                        | percent_numbers(claim_map[i]["quote"])
                bad_pct = sorted(percent_numbers(no_ci) - have_pct)
                if bad_pct:
                    reason = (f"number(s) {bad_pct} given with a % sign, but in the cited "
                              f"claims they have no % sign (unit was added)")
            if not reason and single_evidence and len(ids) == 1:
                item["text"] = claim_map[ids[0]]["claim"]
            if reason:
                item["kind"] = "inference"
                issues.append(f"{section}: [E] downgraded to [AI] — {reason}: "
                              f"{s.text[:70]}")
            else:
                have = set()
                for i in ids:
                    have |= claim_numbers(claim_map[i])
                missing = sorted(numbers(strip_labels(item["text"])) - have)
                if missing and single_evidence:
                    item["kind"] = "inference"
                    issues.append(f"{section}: [E] downgraded to [AI] — numbers {missing} "
                                  f"absent from the cited claim: {s.text[:70]}")
                elif missing:
                    # число, якого немає в цитованих claims (наприклад, сума), — це обчислення
                    # моделі, а не факт з джерела: [E] -> [AI], попередження лишається
                    item["kind"] = "inference"
                    item["unverified_numbers"] = missing
                    issues.append(f"{section}: [E] downgraded to [AI] — numbers {missing} absent "
                                  f"from the cited claims (a calculation, not a fact): {s.text[:70]}")
        if single_evidence and item["kind"] == "inference" and ids:
            # висновок моделі в рекомендації теж не має містити чисел, яких нема в цитованих claims
            have = set()
            for i in ids:
                have |= claim_numbers(claim_map[i])
            txt = re.sub(r"(?i)\d+\s*%\s*(?:CI|confidence interval)", "", item["text"])
            missing = sorted(numbers(strip_labels(txt)) - have)
            if missing:
                issues.append(f"{section}: [AI] removed — numbers {missing} absent from "
                              f"the cited claims: {s.text[:70]}")
                continue
        out.append(item)
    return out

def validate_conflicts(draft: ConflictsDraft, claim_map: dict, issues: list):
    """Перевіряємо id ТА напрямок: у supporting мають бути лише claims із direction
    'supports', у contradicting — лише 'contradicts' (модель інколи плутає боки)."""
    out = []
    used_sup = set()
    for c in draft.conflicts:
        sup = [i for i in c.supporting_claim_ids
               if i in claim_map and claim_map[i]["direction"] == "supports"]
        con = [i for i in c.contradicting_claim_ids
               if i in claim_map and claim_map[i]["direction"] == "contradicts"]
        if len(sup) != len(c.supporting_claim_ids) or \
                len(con) != len(c.contradicting_claim_ids):
            issues.append(f"Conflicts: in topic \"{c.topic[:50]}\" removed ids that "
                          f"do not exist or whose direction does not match the conflict side")
        if not sup or not con:
            issues.append(f"Conflicts: topic \"{c.topic[:50]}\" dropped "
                          f"(no claims on both sides)")
            continue
        if not any(mentions_drug(claim_map[i]) for i in sup) or \
                not any(mentions_drug(claim_map[i]) for i in con):
            issues.append(f"Conflicts: topic \"{c.topic[:50]}\" dropped — one "
                          f"side has no claim about the target drug "
                          f"(a class or another drug versus ours)")
            continue
        if NOT_CONFLICT_RE.search(c.assessment or ""):
            issues.append(f"Conflicts: topic \"{c.topic[:50]}\" dropped — the assessment itself "
                          f"says this is not an empirical contradiction")
            continue
        cs, cc = comparators(sup, claim_map), comparators(con, claim_map)
        if cs and cc and not (cs & cc):
            issues.append(f"Conflicts: topic \"{c.topic[:50]}\" dropped — the sides "
                          f"use different comparators ({sorted(cs)} versus "
                          f"{sorted(cc)})")
            continue
        if set(sup) <= used_sup:
            issues.append(f"Conflicts: topic \"{c.topic[:50]}\" dropped (the same "
                          f"supporting claims are already used in another contradiction)")
            continue
        used_sup |= set(sup)
        status = c.status
        if status == "resolved" and \
                len({claim_map[i].get("evidence_id") for i in sup + con}) > 1:
            
            status = "unresolved"
            issues.append(f"Conflicts: \"{c.topic[:50]}\" — status resolved downgraded to "
                          f"unresolved (the sides come from different studies)")
        assessment = c.assessment or ""
        if status == "unresolved" and RESOLVED_TEXT_RE.search(assessment):
            assessment = RESOLVED_TEXT_RE.sub("", assessment).strip()
            assessment = ("Not resolved: the two sides come from different studies. "
                          + assessment).strip()
        out.append({"topic": c.topic, "endpoint": c.endpoint,
                    "shared_comparator": c.shared_comparator,
                    "supporting": sup, "contradicting": con,
                    "assessment": assessment, "status": status})
    return out

def drop_false_absence(sections: dict, claim_map: dict, issues: list):
    """Якщо в досьє є сильний клінічний claim, прибираємо з розділів твердження й gaps
    на кшталт «немає клінічних даних у людей»: вони суперечать самому досьє."""
    lead = lead_efficacy_item(claim_map)
    if not lead:
        return
    lid = lead["claim_ids"][0]
    for sec in sections.values():
        kept = []
        for st in sec["statements"]:
            if says_no_human_data(st["text"]):
                issues.append(f"{sec['title']}: statement removed — it says that "
                              f"there are no clinical data in humans, but the dossier has {lid}: "
                              f"{st['text'][:70]}")
            else:
                kept.append(st)
        sec["statements"] = kept
        gaps = []
        for g in sec["gaps"]:
            if says_no_human_data(g):
                issues.append(f"{sec['title']}: gap removed — contradicts {lid}: {g[:70]}")
            else:
                gaps.append(g)
        sec["gaps"] = gaps
   
# Твердження про відсутність ПОРІВНЯЛЬНИХ даних («немає head-to-head») — не те саме, що
# «немає клінічних даних у людей». Їх не чіпаємо цим правилом.
COMPARATIVE_RE = re.compile(r"(?i)head[- ]to[- ]head|comparative|comparison|\bversus\b|\bvs\.?\b|"
                            r"direct(?:ly)? compar|active comparator|other agents|competitor")

def says_no_human_data(text: str) -> bool:
    t = text or ""
    if COMPARATIVE_RE.search(t) or other_drugs_in(t):
        return False
    return any(r.search(t) for r in NO_HUMAN_DATA_RES)

def comparators(ids: list, claim_map: dict) -> set:
    """Із якими компараторами порівнюють claims: placebo / active (за текстом claim)."""
    out = set()
    for i in ids:
        t = claim_map[i]["claim"]
        if PLACEBO_RE.search(t):
            out.add("placebo")
        if ACTIVE_RE.search(t):
            out.add("active")
    return out

def lead_efficacy_item(claim_map: dict):
    """Найсильніший клінічний claim про ефективність (supports, high, є % і placebo)."""
    best, best_sc = None, 0.0
    for c in claim_map.values():
        if c.get("direction") != "supports" or c.get("stage") != "clinical" \
                or c.get("confidence") != "high" or c.get("drug_not_in_quote"):
            continue
        t = c.get("claim", "")
        t_nci = re.sub(r"(?i)\d+\s*%\s*(?:CI|confidence interval)", "", t)
        if not (re.search(r"(?i)placebo", t) and re.search(r"\d\s*%", t_nci)):
            continue
        sc = claim_strength(c)
        if sc > best_sc:
            best, best_sc = c, sc
    if not best:
        return None
    return {"text": best["claim"], "kind": "evidence", "claim_ids": [best["id"]],
            "unverified_numbers": []}

def claim_strength(c: dict) -> float:
    """Груба «сила» клінічного claim: пізніша фаза, висока впевненість, більший ефект."""
    t = c.get("claim", "")
    sc = 0.0
    if re.search(r"(?i)phase\s*(?:3|iii)\b|triumph|\bfda\b", t):
        sc += 30
    if c.get("confidence") == "high":
        sc += 5
    if re.search(r"(?i)placebo", t):
        sc += 10
    t_nci = re.sub(r"(?i)\d+\s*%\s*(?:CI|confidence interval)", "", t)
    pcts = [float(x.replace(",", ".")) for x in
            re.findall(r"(\d+(?:[.,]\d+)?)\s*%", t_nci)]
    if pcts:
        sc += min(max(pcts), 40) / 4
    return sc

def _ot_label_mismatch(text: str, ids: list, claim_map: dict) -> bool:
    """Open Targets: «overall» бал об'єднує типи доказів. Якщо текст називає тип
    (genetic/clinical/literature), має бути claim із цим словом і з числом, що є в тексті."""
    nums_text = numbers(strip_labels(text))
    for kw in ("genetic", "clinical", "literature"):
        if re.search(rf"(?i)\b{kw}", text):
            ok = any(kw in claim_map[i]["claim"].lower()
                     and (numbers(strip_labels(claim_map[i]["claim"])) & nums_text)
                     for i in ids)
            if not ok:
                return True
    return False
     
def mentions_drug(c: dict) -> bool:
    """Чи згадує claim (текст, цитата, заголовок запису) цільовий препарат."""
    if not DRUG_NAMES:
        return True
    t = " ".join([c.get("claim", ""), c.get("quote", ""),
                  c.get("record_title") or ""]).lower()
    return any(nm in t for nm in DRUG_NAMES)

def order_rationale(items: list, claim_map: dict, flag_ids: set = None) -> list:
    """Рекомендація: спочатку [E] «за» (найсильніший клінічний результат першим),
    потім [E] червоні прапори, потім інші [E] про ризики (contradicts), потім [AI]."""
    flag_ids = flag_ids or set()
    ev = [x for x in items if x["kind"] == "evidence" and x["claim_ids"]]
    rest = [x for x in items if x not in ev]

    def key(x):
        risk = any(claim_map[i].get("direction") == "contradicts" for i in x["claim_ids"])
        flag = any(i in flag_ids for i in x["claim_ids"])
        grp = 1 if flag else (2 if risk else 0)
        return (grp, -max(claim_strength(claim_map[i]) for i in x["claim_ids"]))
    ev.sort(key=key)
    return ev + rest


def conflict_risk_items(conflicts: list, claim_map: dict, rationale: list, n: int = 2) -> list:
    """Рекомендація не може мовчати про нерозв'язану суперечність. Для кожної такої
    суперечності беремо найсильніший заперечуючий claim (не low-confidence), якщо
    рекомендація його ще не цитує як [E], і додаємо як [E]. Максимум n штук."""
    have = {i for x in rationale if x["kind"] == "evidence" for i in x["claim_ids"]}
    out = []
    for c in conflicts:
        if c.get("status") != "unresolved":
            continue
        cands = [claim_map[i] for i in c.get("contradicting", []) if i in claim_map
                 and claim_map[i].get("confidence") != "low"]
        if not cands or any(x["id"] in have for x in cands):
            continue
        best = max(cands, key=claim_strength)
        out.append({"text": best["claim"], "kind": "evidence", "claim_ids": [best["id"]],
                    "unverified_numbers": [], "from_conflict": c.get("topic", "")})
        have.add(best["id"])
        if len(out) >= n:
            break
    return out


def key_efficacy_items(claim_map: dict, cited: set, n: int = 3) -> list:
    """Найсильніші клінічні результати ефективності (supports, high, плацебо і %), яких
    не процитував жоден розділ. Код додає їх у Clinical development plan як [E]."""
    cands = []
    for c in claim_map.values():
        if c["id"] in cited or c.get("direction") != "supports" \
                or c.get("stage") != "clinical" or c.get("confidence") != "high" \
                or c.get("drug_not_in_quote"):
            continue
        t = c.get("claim", "") + " " + c.get("quote", "")   # % і плацебо можуть бути лише в цитаті
        t_nci = re.sub(r"(?i)\d+\s*%\s*(?:CI|confidence interval)", "", t)
        if not (re.search(r"(?i)placebo", t) and re.search(r"\d\s*%", t_nci)):
            continue
        cands.append((claim_strength(c), c))
    cands.sort(key=lambda x: -x[0])
    return [{"text": c["claim"], "kind": "evidence", "claim_ids": [c["id"]],
             "unverified_numbers": []} for _, c in cands[:n]]

def cross_trial_item(claim_map: dict):
    """Непряме порівняння ефективності: головний результат цільового препарату (плацебо-контроль)
    і claim про середню втрату ваги інших препаратів. Це висновок, а не факт: інші дослідження."""
    lead = lead_efficacy_item(claim_map)
    if not lead:
        return None
    best = None
    for c in claim_map.values():
        t = c.get("claim", "")
        if c.get("stage") != "competition" or mentions_drug(c):
            continue
        if not (re.search(r"(?i)weight (?:loss|reduction)", t) and re.search(r"\d\s*%", t)
                and other_drugs_in(t)):
            continue
        if best is None or c.get("confidence") == "high" and best.get("confidence") != "high":
            best = c
    if not best:
        return None
    a = lead["text"].rstrip(". ")
    b = best["claim"].rstrip(". ")
    return {"text": (f"Indirect cross-study comparison, not a head-to-head trial. {a}. "
                     f"Other agents: {b}. The studies differ in populations, doses and duration, "
                     f"so this does not prove that this drug is better."),
            "kind": "inference", "claim_ids": [lead["claim_ids"][0], best["id"]],
            "unverified_numbers": []}


def claim_numbers(claim: dict) -> set:
    return numbers(claim["claim"]) | numbers(claim["quote"])

def other_drugs_in(text: str) -> list:
    """Назви препаратів у тексті, яких немає серед імен цільового препарату."""
    return sorted({m.group(0).lower() for m in INN_RE.finditer(text or "")}
                  - {n.lower() for n in DRUG_NAMES})


# ---------------------------------------------------------------- червоні прапори

HOLD_RE = re.compile(r"(?i)clinical hold")
HOLD_LIFTED_RE = re.compile(r"(?i)\b(?:lifted|released|removed|resolved)\b|no clinical hold|not (?:been )?placed")
DEATH_RE = re.compile(r"(?i)\b(?:deaths?|died|fatal(?:ity|ities)?)\b")
NO_DEATH_RE = re.compile(r"(?i)\b(?:no|zero|0)\s+(?:\w+[- ])?deaths?\b|death\s*\(0\)|deaths?:?\s*0\b")
DRUG_REL_RE = re.compile(r"(?i)drug[- ]induced|drug[- ]related|treatment[- ]related|"
                         r"attributed to|probabl[ye] related|caused by|related to (?:the )?(?:study )?(?:drug|treatment)")
SAFETY_STOP_RE = re.compile(r"(?i)(?:programme?|development|trials?|studies|enrol?lment)[^.;]{0,50}"
                            r"\b(?:terminated|halted|suspended|paused)\b")
SAFETY_WORD_RE = re.compile(r"(?i)safety|liver|hepat|toxicit|adverse|death|injury")

def red_flag_kind(c: dict):
    """Тип «червоного прапора» для claim або None. Прапор = впевнений (high) claim, що
    суперечить тезі, про цільовий препарат, і каже про: клінічний hold FDA, смерть,
    пов'язану з препаратом, або зупинку програми/досліджень з міркувань безпеки."""
    if c.get("direction") != "contradicts" or c.get("confidence") != "high":
        return None
    if c.get("source_type") == "nct_aact_population" or c.get("drug_not_in_quote"):
        return None
    if not mentions_drug(c):
        return None
    t = c.get("claim", "")
    if HOLD_RE.search(t) and not HOLD_LIFTED_RE.search(t):
        return "FDA clinical hold"
    if DEATH_RE.search(t) and not NO_DEATH_RE.search(t) and DRUG_REL_RE.search(t):
        return "drug-related death"
    if SAFETY_STOP_RE.search(t) and SAFETY_WORD_RE.search(t):
        return "programme/trials halted for safety"
    return None

def red_flags(claim_map: dict) -> list:
    out = []
    for c in claim_map.values():
        k = red_flag_kind(c)
        if k:
            out.append({"id": c["id"], "kind": k, "claim": c["claim"],
                        "is_extra": bool(c.get("is_extra"))})
    return out

LEVELS = ["Do Not Invest", "Conditional", "Invest"]

def downgrade_recommendation(rec: str) -> str:
    """На один рівень вниз: Invest -> Conditional -> Do Not Invest."""
    return LEVELS[max(0, LEVELS.index(rec) - 1)]

STOP_CATEGORIES = {"death_or_life_threatening_harm", "regulatory_halt_or_refusal",
                   "programme_terminated", "failed_pivotal_trial", "invalid_key_result"}

def expected_after_flags(base: str, flags: list) -> str:
    """Найвищий рівень, дозволений після критичних знахідок. Категорії «зупиняє програму»
    (смерть, регуляторна зупинка, закриття, провал реєстраційного дослідження, недійсний
    ключовий результат) дають Do Not Invest; інша критична знахідка — на один рівень нижче.
    Категорію ставить модель-тріаж; для знахідок лише від запасного фільтру категорії немає,
    і вони вважаються «зупиняє програму» (фільтр ловить лише такі події)."""
    if any((f.get("category") is None) or f.get("category") in STOP_CATEGORIES for f in flags):
        return "Do Not Invest"
    return downgrade_recommendation(base)

def new_evidence_items(claim_map: dict, rationale: list, flag_ids: set, n: int = 3) -> list:
    """Найважливіші НОВІ claims (is_extra, high), яких ще немає в Recommendation як [E].
    Спершу червоні прапори, потім claims про безпеку/порівняння з конкурентом."""
    have = {i for x in rationale if x["kind"] == "evidence" for i in x["claim_ids"]}
    cands = []
    for c in claim_map.values():
        if not c.get("is_extra") or c.get("confidence") != "high" or c["id"] in have:
            continue
        if c.get("direction") not in ("supports", "contradicts"):
            continue
        pr = 0 if c["id"] in flag_ids else (1 if c.get("stage") in ("competition", "safety_or_failure",
                                                                     "regulatory") else 2)
        cands.append((pr, c["id"], c))
    cands.sort(key=lambda x: (x[0], x[1]))
    return [{"text": c["claim"], "kind": "evidence", "claim_ids": [c["id"]],
             "unverified_numbers": []} for _, _, c in cands[:n]]

H2H_ABSENCE_RE = re.compile(r"(?i)\b(?:no|not|lack(?:s|ing)?|absence of|without|unavailable)\b[^.;]{0,90}"
                            r"head[- ]to[- ]head|head[- ]to[- ]head[^.;]{0,60}\b(?:not|no|lack|absent|unavailable)\b|"
                            r"no (?:publicly )?available[^.;]{0,60}(?:comparative|versus)")

def has_head_to_head(claim_map: dict):
    """Claim із результатом прямого порівняння цільового препарату з іншим (числа + head-to-head)."""
    for c in claim_map.values():
        t = c.get("claim", "")
        if re.search(r"(?i)head[- ]to[- ]head", t) and re.search(r"\d", t) \
                and mentions_drug(c) and other_drugs_in(t):
            return c
    return None

def drop_false_h2h_absence(sections: dict, rationale: list, claim_map: dict, issues: list):
    """Якщо в досьє є результат head-to-head, прибираємо твердження «head-to-head даних немає».
    Повертає rationale без таких тверджень."""
    h = has_head_to_head(claim_map)
    if not h:
        return rationale
    def bad(text):
        return bool(H2H_ABSENCE_RE.search(text or ""))
    for sec in sections.values():
        kept = []
        for st in sec["statements"]:
            if bad(st["text"]):
                issues.append(f"{sec['title']}: statement removed — says there is no head-to-head data "
                              f"but the dossier has {h['id']}: {st['text'][:70]}")
            else:
                kept.append(st)
        sec["statements"] = kept
        sec["gaps"] = [g for g in sec["gaps"] if not bad(g)]
    out = []
    for st in rationale:
        if bad(st["text"]):
            issues.append(f"Recommendation: statement removed — says there is no head-to-head data "
                          f"but the dossier has {h['id']}: {st['text'][:70]}")
        else:
            out.append(st)
    return out


# ---------------------------------------------------------------- тріаж тяжкості (модель)

class Severity(BaseModel):
    claim_id: str
    level: Literal["critical", "major"]
    category: Literal["death_or_life_threatening_harm", "regulatory_halt_or_refusal",
                      "programme_terminated", "failed_pivotal_trial",
                      "invalid_key_result", "other_equivalent_weight", "not_critical"] = Field(
        description="Why it is critical. Use not_critical when level is major.")
    reason: str = Field(description="One short sentence: why this level.")

class TriageDraft(BaseModel):
    items: list[Severity]

def validate_triage(draft: TriageDraft, claim_map: dict, issues: list) -> list:
    """Лишає тільки перевірювані оцінки моделі: id існує, claim про цільовий препарат,
    не умови включення. «critical» з low-confidence claim знижуємо до «major»."""
    out = []
    for it in draft.items:
        c = claim_map.get(it.claim_id)
        if not c:
            issues.append(f"Triage: id {it.claim_id} does not exist — assessment dropped")
            continue
        if c.get("source_type") == "nct_aact_population" or c.get("drug_not_in_quote") \
                or not mentions_drug(c):
            issues.append(f"Triage: {it.claim_id} is not about the target drug — assessment dropped")
            continue
        level = it.level
        if level == "critical" and c.get("confidence") == "low":
            level = "major"
            issues.append(f"Triage: {it.claim_id} \"critical\" downgraded to \"major\" — low-confidence claim")
        if level == "critical" and it.category == "not_critical":
            level = "major"
            issues.append(f"Triage: {it.claim_id} \"critical\" without a category — downgraded to \"major\"")
        out.append({"id": c["id"], "level": level, "category": it.category,
                    "reason": it.reason.strip()})
    return out

def merge_flags(triage: list, claim_map: dict) -> list:
    """Критичні знахідки = (модель оцінила critical) ∪ (запасний ключовий фільтр).
    Модель ловить невідомі типи подій; фільтр страхує від її нестабільності."""
    by_id = {}
    for t in triage:
        if t["level"] == "critical":
            c = claim_map[t["id"]]
            by_id[t["id"]] = {"id": t["id"], "kind": "critical finding", "claim": c["claim"],
                              "reason": t["reason"], "category": t.get("category"),
                              "found_by": ["model"],
                              "is_extra": bool(c.get("is_extra"))}
    for f in red_flags(claim_map):
        if f["id"] in by_id:
            by_id[f["id"]]["found_by"].append("keywords")
            by_id[f["id"]]["kind"] = f["kind"]
        else:
            f = dict(f)
            f["reason"] = "matched the backstop keyword rule"
            f["found_by"] = ["keywords"]
            by_id[f["id"]] = f
    return sorted(by_id.values(), key=lambda x: x["id"])