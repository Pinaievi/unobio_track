import re
from typing import Literal
from pydantic import BaseModel, Field
from text_utils import *


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

DRUG_NAMES: set = set()

PLACEBO_RE = re.compile(r"(?i)\bplacebo\b|control group|control arm|\bcontrols?\b")
ACTIVE_RE = re.compile(r"(?i)other (?:incretin|glp|treatment|therap|drug|agent)|"
                       r"tirzepatide|semaglutide|dulaglutide|liraglutide|"
                       r"active comparator|danuglipron")

RISK_ASSOC_RE = re.compile(r"(?i)hazard ratio|\bHR\b|odds ratio|\bOR\b\s*[=:]?\s*\d|relative risk")

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
    r"\b(?:lack|absence) of\b|\bno FDA[- ]approved\b|\bnot (?:yet )?(?:been )?(?:published|reported)\b")

SOURCES_RE = re.compile(r"(?i)(?:retrieved|provided|available|reviewed|these|the) sources|"
                        r"in the (?:claims|dossier|records)|not covered by")

MECH_STAGES = {"mechanism", "translation"}

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
            issues.append(f"{section}: вигадані id {bad} прибрано")
        item = {"text": s.text, "kind": s.kind, "claim_ids": ids,
                "unverified_numbers": []}
        gap = GAP_RE.search(s.text)
        if gap and not SOURCES_RE.search(s.text):
            if gap.start() <= 12:
                item["text"] = ("In the retrieved sources: " + s.text[0].lower() + s.text[1:])

            if s.kind == "evidence":
                item["kind"] = "inference"
            issues.append(f"{section}: твердження про відсутність даних -> [AI]"
                          f"{' з приміткою про джерела' if gap.start() <= 12 else ''}: "
                          f"{s.text[:70]}")
        if single_evidence and ids and item["kind"] == "evidence" \
                and all(claim_map[i]["stage"] in MECH_STAGES for i in ids):
            issues.append(f"{section}: тривіальний [E] про механізм прибрано з "
                          f"рекомендації (він є в розділі 1): {s.text[:70]}")
            continue
        if item["kind"] == "evidence":
            if not ids:
                issues.append(f"{section}: evidence без claims відкинуто: "
                              f"{s.text[:70]}")
                continue
            if section.startswith("Commercial") and all(
                    claim_map[i].get("source_type") == "nct_aact_population" for i in ids):
                
                issues.append(f"{section}: [E] лише на критеріях включення в дослідження "
                              f"(не показник ринку) відкинуто: {s.text[:70]}")
                continue
            families = {claim_map[i]["stage"] in MECH_STAGES for i in ids}
            dirs = {claim_map[i]["direction"] for i in ids}
            reason = None
            if len(families) > 1:
                reason = "поєднує біологію/PK і клінічні дані"
            elif {"supports", "contradicts"} <= dirs:
                reason = "поєднує claims із протилежними напрямками"
            elif len({claim_map[i].get("evidence_id") for i in ids}) > 1 \
                    and CROSS_LINK_RE.search(s.text):
                reason = ("зіставляє claims із різних записів (порівняння/зміна "
                          "між джерелами — це висновок моделі, не факт)")
            elif any(claim_map[i].get("source_type") == "opentargets" for i in ids) \
                    and _ot_label_mismatch(s.text, ids, claim_map):
                reason = ("тип доказу (genetic/clinical/literature) для балу Open Targets "
                          "названо, але цитовані claims не дають такого балу з цими числами")
            elif any(claim_map[i].get("confidence") == "low" for i in ids):
                reason = "серед цитованих claims є low-confidence: не подаємо як факт"
            elif section.startswith("Commercial") \
                    and len({claim_map[i].get("evidence_id") for i in ids}) > 1 \
                    and len(numbers(strip_labels(s.text))) >= 2:
                reason = ("у комерції числа з різних записів в одному [E] "
                          "(можуть бути різні показники)")
            elif section.startswith("Commercial") and RISK_ASSOC_RE.search(s.text):
                reason = ("ризик-асоціація (HR/OR) описує хворобу, а не розмір ринку: "
                          "не подаємо як факт про комерційну можливість")
            elif single_evidence and len(ids) > 1:
                reason = "у рекомендації факт має спиратися на один claim"
            elif single_evidence and any(
                    claim_map[i].get("confidence") == "low"
                    or claim_map[i].get("source_type") == "epmc_ppr" for i in ids):
                reason = "у рекомендації не можна подавати low-confidence/препринт як факт"
            if not reason:

                no_ci = re.sub(r"(?i)\d+\s*%\s*(?:CI|confidence interval)", "", item["text"])
                have_pct = set()
                for i in ids:
                    have_pct |= percent_numbers(claim_map[i]["claim"]) \
                        | percent_numbers(claim_map[i]["quote"])
                bad_pct = sorted(percent_numbers(no_ci) - have_pct)
                if bad_pct:
                    reason = (f"число(а) {bad_pct} подано зі знаком % , а в цитованих "
                              f"claims їх немає зі знаком % (одиницю дописано)")
            if not reason and single_evidence and len(ids) == 1:
                item["text"] = claim_map[ids[0]]["claim"]
            if reason:
                item["kind"] = "inference"
                issues.append(f"{section}: [E] знижено до [AI] — {reason}: "
                              f"{s.text[:70]}")
            else:
                have = set()
                for i in ids:
                    have |= claim_numbers(claim_map[i])
                missing = sorted(numbers(strip_labels(item["text"])) - have)
                if missing and single_evidence:
                    item["kind"] = "inference"
                    issues.append(f"{section}: [E] знижено до [AI] — числа {missing} "
                                  f"відсутні в цитованому claim: {s.text[:70]}")
                elif missing:
                    item["unverified_numbers"] = missing
                    issues.append(f"{section}: числа {missing} відсутні в цитованих "
                                  f"claims: {s.text[:70]}")
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
            issues.append(f"Conflicts: у темі «{c.topic[:50]}» прибрано id, яких "
                          f"немає або чий напрямок не збігається з боком конфлікту")
        if not sup or not con:
            issues.append(f"Conflicts: тему «{c.topic[:50]}» відкинуто "
                          f"(немає claims з обох боків)")
            continue
        if not any(mentions_drug(claim_map[i]) for i in sup) or \
                not any(mentions_drug(claim_map[i]) for i in con):
            issues.append(f"Conflicts: тему «{c.topic[:50]}» відкинуто — з одного "
                          f"боку немає жодного claim про цільовий препарат "
                          f"(клас або інший препарат проти нашого)")
            continue
        if NOT_CONFLICT_RE.search(c.assessment or ""):
            issues.append(f"Conflicts: тему «{c.topic[:50]}» відкинуто — сама оцінка "
                          f"каже, що це не емпіричне протиріччя")
            continue
        cs, cc = comparators(sup, claim_map), comparators(con, claim_map)
        if cs and cc and not (cs & cc):
            issues.append(f"Conflicts: тему «{c.topic[:50]}» відкинуто — сторони "
                          f"порівнюють із різним компаратором ({sorted(cs)} проти "
                          f"{sorted(cc)})")
            continue
        if set(sup) <= used_sup:
            issues.append(f"Conflicts: тему «{c.topic[:50]}» відкинуто (ті самі "
                          f"supporting claims уже використані в іншій суперечності)")
            continue
        used_sup |= set(sup)
        status = c.status
        if status == "resolved" and \
                len({claim_map[i].get("evidence_id") for i in sup + con}) > 1:
            
            status = "unresolved"
            issues.append(f"Conflicts: «{c.topic[:50]}» — статус resolved знижено до "
                          f"unresolved (сторони з різних досліджень)")
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
                issues.append(f"{sec['title']}: твердження прибрано — воно каже, що "
                              f"клінічних даних у людей немає, але в досьє є {lid}: "
                              f"{st['text'][:70]}")
            else:
                kept.append(st)
        sec["statements"] = kept
        gaps = []
        for g in sec["gaps"]:
            if says_no_human_data(g):
                issues.append(f"{sec['title']}: gap прибрано — суперечить {lid}: {g[:70]}")
            else:
                gaps.append(g)
        sec["gaps"] = gaps
   
def says_no_human_data(text: str) -> bool:
    return any(r.search(text or "") for r in NO_HUMAN_DATA_RES)

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

def order_rationale(items: list, claim_map: dict) -> list:
    """Рекомендація: спочатку [E] (найсильніший клінічний результат першим), потім [AI]."""
    ev = [x for x in items if x["kind"] == "evidence" and x["claim_ids"]]
    rest = [x for x in items if x not in ev]
    ev.sort(key=lambda x: -max(claim_strength(claim_map[i]) for i in x["claim_ids"]))
    return ev + rest

def claim_numbers(claim: dict) -> set:
    return numbers(claim["claim"]) | numbers(claim["quote"])
