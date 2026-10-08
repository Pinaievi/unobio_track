import argparse
import json
from datetime import date, datetime
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Literal

import dotenv
from google import genai
from pydantic import BaseModel, Field
from text_utils import *

MODEL = "gemini-3.1-flash-lite"      
FINAL_MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3

PRICE_IN_PER_M = 0.10
PRICE_OUT_PER_M = 0.40

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

REMAINING_FLOOR = 0.10

ROOT = Path(__file__).resolve().parent
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
INDICATION_WORDS: set = set()
INDICATION_SYNONYMS = {"obesity": ["overweight", "weight", "adipos", "bmi", "bariatric"]}
DRUG_NAMES: set = set()

COMMON_RULES = """
You are a biotech investment analyst writing one section of an underwriting report.
You receive a numbered list of CLAIMS. Each claim was extracted from a source record and
its quote was verified. This list is your ONLY source of facts.

RULES:
1. Use only facts from the provided claims. No outside knowledge, no invented numbers.
2. Every statement has kind "evidence" or "inference".
   - "evidence": restates what the cited claims say. Every number in it must appear in
     the cited claims.
   - "inference": your own reasoning (a conclusion, an implication, an estimate). Say
     clearly that it is an inference. It must cite the claims it rests on.
3. Cite claim ids ONLY in the claim_ids field, exactly as given (for example C012).
   Never write ids inside the statement text. Never invent ids.
4. Look for contradicting evidence. If any claim has direction "contradicts", it must
   be addressed in the section, not ignored. Never present a claim as support for a
   statement it does not say.
5. Weight claims by confidence and source type: preprints, animal or cell data, ex vivo
   tissue, single cases and trial registry entries without results are weak evidence.
   A registered or recruiting trial is NOT evidence that the drug works. Placebo is a
   control, not a competitor.
6. If the claims do not cover something this section needs, do not fill the hole with
   guesses. List it in "gaps".
7. Write 3 to 8 statements. Short, concrete, no marketing language.
8. If a statement connects facts from DIFFERENT claims (cause and effect, correlation,
   "which leads to", a comparison between sources), it is an inference, not evidence.
   Mark it as "inference". Use kind "evidence" only for what a single claim says or
   for a plain list of facts that each claim states on its own.
9. Do not call a drug approved, a standard of care or a competitor unless a claim says
   so. A claim that a drug's label text mentions an indication does not mean the drug
   is approved for it.
10. A missing record in a database (for example "no label found in openFDA") only
   shows that no record was found. Do not state "not approved" or "no regulatory
   status" as evidence: write "no label record was found in openFDA", or mark the
   conclusion as an inference.
11. Do not add facts that no cited claim states (for example "nearing completion",
   "large-scale", "positive preclinical data"). If you need such a statement, it is an
   inference and must say what it rests on.
12. The claims you see are only the part of the dossier relevant to this section; other
   sections hold other claims. Never write that data "does not exist" or "was not
   provided" for the whole project (for example "no human trial data"). Write gaps as
   "not covered by the claims of this section" or as concrete questions to check.
14. Every claim with direction "supports" or "contradicts" in your list must be used in
   a statement, or its omission explained in "gaps" (for example because it concerns
   another drug). Do not silently skip the strongest positive or negative claims.
15. Do not call a trend "dose-dependent", "dose-related" or "increasing with dose" in
   your own words unless the cited numbers actually rise with the dose in order (for
   example 4% then 12% then 8% is NOT monotonic: say the rates differ by dose and give
   the numbers). Do not generalise from one trial to the whole drug.
13. The percentage of participants with ANY adverse event in a Phase 1, healthy-volunteer
   or small dose-escalation cohort is not a safety signal by itself: nearly all
   participants report some event. Do not call it a "high incidence" or a "safety
   concern" unless a cited claim compares it with placebo or reports serious or
   treatment-related events. Say what was measured and that the comparison is missing.
"""

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

CONFLICTS_TASK = """
You are a skeptical due-diligence analyst. Below are claims that support {drug} and
claims that contradict it (direction supports / contradicts). Find the disagreements:
topics where one or more claims point one way and one or more point the other way
(for example: efficacy vs tolerability, safety in a meta-analysis vs a single trial,
animal results vs human results).

RULES:
1. A conflict needs at least one supporting AND at least one contradicting claim that
   measure the SAME endpoint in a comparable setting (same outcome, same kind of
   population). Do not pair unrelated claims.
1b. Both sides must use the SAME comparator (for example both against placebo). A
   result against placebo and a result against other drugs are different questions:
   do not pair them. Fill endpoint and shared_comparator honestly. Prefer pairs where
   both sides are randomised trials or meta-analyses; a low-certainty claim, a single
   case or animal data does not balance a trial result (reflect that in status).
2. Not a conflict: a trade-off inside one result (for example a higher dose gives more
   weight loss and more dropouts), a general safety summary versus one specific adverse
   event, or animal results versus a human result of a different outcome.
3. Every conflict must be about a DIFFERENT topic. A claim may be the supporting side
   of only one conflict. Do not repeat the same pair under another title.
4. Cite claim ids only in the id lists, exactly as given. Never invent ids. Do not
   write ids inside the text.
5. assessment is your inference: weigh confidence, source type, dose, population and
   stated certainty. status "resolved" only if one side is clearly stronger on the
   evidence given; otherwise "unresolved".
6. 0 to 4 conflicts. If there are no real conflicts, return an empty list: that is a
   valid answer.
7. These are NOT conflicts, do not output them: two claims that describe the same effect
   in different words (for example "statistically significant" versus "modest"); a
   mechanistic hypothesis or preclinical rationale versus an observed clinical result;
   a class-wide finding versus a finding about one specific drug. If your assessment
   would say "not an empirical contradiction", leave the topic out.
8. Each side must contain at least one claim that is about {drug} itself. A finding
   about another drug or a whole drug class versus a finding about {drug} is not a
   conflict; a review's general statement versus one specific trial is not a conflict.
"""

FINAL_TASK = """
You are the investment committee analyst. Below are the drafted sections of the report,
the conflicts found between supporting and contradicting evidence, the capital
estimate, and the counts of claims by stage and direction. Produce the final part of
the report.

RULES:
1. recommendation is one of "Invest", "Conditional", "Do Not Invest".
   - Default to "Conditional" when critical unknowns remain or conflicts are unresolved.
   - "Invest" only if the evidence is strong, human efficacy and safety are shown in the
     claims, and no unresolved contradicting evidence is material.
   - "Do Not Invest" if the claims show failure or a serious unresolved safety problem.
2. recommendation_rationale: 3 to 6 statements that justify the recommendation and cite
   claim ids. Use kind "evidence" ONLY for a statement that restates a SINGLE claim
   (cite that one id). Every conclusion, weighing, or link between claims (mechanism
   plus clinical result, efficacy versus tolerability, etc.) is kind "inference". Include the strongest argument for AND the strongest argument against,
   and address the unresolved conflicts. Do not write claim ids inside the text.
   Keep the strength of every cited claim: if its confidence is "low" or "medium", or it
   comes from an indirect comparison / network meta-analysis / preprint / subgroup, say so
   in the text ("low-certainty", "indirect comparison", "preliminary"). Never turn such a
   claim into a firm statement about competitors (for example "worse than competitors"):
   a comparison with other drugs is allowed only if a cited claim is a direct head-to-head
   trial; otherwise write that the signal comes from indirect data and needs confirmation.
2b. Lead the rationale with the strongest PEER-REVIEWED human result (for example a
   randomised trial with its comparator) and the strongest safety result. Company-reported
   or not-yet-peer-reviewed numbers may be used only as an inference with that caveat.
   Write each such result as its OWN [E] statement that cites exactly ONE claim (for
   example one dose of one randomised trial); do not merge several claims or several
   papers into one statement, otherwise the statement is downgraded to [AI].
3. critical_unknowns: facts that, if known, would change the recommendation. Concrete.
4. diligence_questions: 5 to 10 questions a diligence team should ask the company or
   check in data. Each must be specific and answerable.
5. what_would_change_the_conclusion: concrete new evidence that would move the
   recommendation up or down (for example a specific kind of trial result).
6. Use only the facts in the sections and claims. Cite claim ids exactly as given.
7. Do not present any-adverse-event percentages from Phase 1 or healthy-volunteer cohorts
   as a safety problem unless the claims compare them with placebo. Do not list as a
   critical unknown something that the KNOWN NAMES line already answers.
8. Do not use kind "evidence" for a bare mechanism-of-action fact; start with the
   strongest clinical or safety claim. A gap in the claims (for example "no clinical
   data") is a statement about the retrieved sources, not about the drug: write "the
   retrieved sources contain no ..." and mark it "inference".
"""

TRUNC_RE = re.compile(r"(?:[;,(=<>±:]|\s[a-z])$")
LOW_CERT_RE = re.compile(
    r"(?i)\b(?:very )?low[- ](?:certainty|quality)\b|not yet peer[- ]reviewed|"
    r"company[- ]reported|press release|unpublished|\bpreliminary (?:data|results)")
YEAR_RE = re.compile(r"^(?:19|20|21)\d\d$")

NOISE_UNMET_RE = re.compile(
    r"(?i)\b(?:veterans?|rural|autis\w*|omega-?\d|social vulnerability|"
    r"hazard ratio|odds ratio|risk of developing|"
    r"associated with (?:an? )?(?:increased|higher|lower|reduced|greater) (?:risk|odds))\b")

NOISE_FLOW_RE = re.compile(r"(?i)lost to follow-?up|withdrawal by subject")
NOISE_ANY_RE = re.compile(
    r"(?i)\b(?:caregivers?|study partners?|informants?|thyroid|anti-?doping|"
    r"doping control|plasma detection window)\b")

NOISE_FLOW_ONE_RE = re.compile(r"(?i)\b(?:one|1|two|2) participants?\b")
MIN_QUOTE_LEN = 25

GAP_RE = re.compile(
    r"(?i)\b(?:no|not any|without any)\s+(?:published\s+|publicly\s+available\s+|"
    r"reported\s+|available\s+)*(?:clinical|human|efficacy|safety|trial|data)|"
    r"\b(?:lack|absence) of\b|\bno FDA[- ]approved\b|\bnot (?:yet )?(?:been )?(?:published|reported)\b")
SOURCES_RE = re.compile(r"(?i)(?:retrieved|provided|available|reviewed|these|the) sources|"
                        r"in the (?:claims|dossier|records)|not covered by")

INN_RE = re.compile(
    r"(?i)\b[a-z]{3,}(?:mab|tug|cept|tinib|rasib|parib|ciclib|stat|tide|glutide|"
    r"siran|gene|vir|tecan|degib|sertib|lisib|zomib)\b")
OTHER_DRUG_STAGES = {"translation", "mechanism", "clinical", "safety_or_failure"}

ENROLLING = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}

NOT_CONFLICT_RE = re.compile(
    r"(?i)not an? (?:true |real |direct |empirical )*(?:contradiction|conflict)|"
    r"matter of (?:clinical )?(?:judg|interpret)|mechanistic hypothesis|"
    r"not (?:really )?contradict")

CROSS_LINK_RE = re.compile(
    r"(?i)\bfrom\b[^.]{0,40}\d[^.]{0,20}\bto\b[^.]{0,20}\d|"
    r"\b(?:rose|rise[ns]?|risen|higher than|lower than|whereas|building on|"
    r"consistent with|confirm\w*)\b")

PLACEBO_RE = re.compile(r"(?i)\bplacebo\b|control group|control arm|\bcontrols?\b")
ACTIVE_RE = re.compile(r"(?i)other (?:incretin|glp|treatment|therap|drug|agent)|"
                       r"tirzepatide|semaglutide|dulaglutide|liraglutide|"
                       r"active comparator|danuglipron")

RISK_ASSOC_RE = re.compile(r"(?i)hazard ratio|\bHR\b|odds ratio|\bOR\b\s*[=:]?\s*\d|relative risk")

NO_HUMAN_DATA_RES = [
    re.compile(r"(?i)\b(?:do(?:es)? not|did not|no|without|lack(?:s|ing)?|absence of)\b"
               r"[^.;]{0,80}\b(?:results? (?:from|of) (?:human )?clinical (?:trials?|studies)"
               r"|human (?:clinical )?(?:trials?|data|results|efficacy|evidence)"
               r"|clinical (?:trial|efficacy|outcome) (?:data|results))"),
    re.compile(r"(?i)clinical efficacy[^.;]{0,80}(?:preclinical|case report)"),
    re.compile(r"(?i)\bpreclinical\b[^.;]{0,40}\b(?:and|plus)\b[^.;]{0,20}\bcase report"),
]

MECH_STAGES = {"mechanism", "translation"}
RESOLVED_TEXT_RE = re.compile(
    r"(?i)\b(?:the )?(?:conflict|issue|dispute|question) (?:is|was|can be) "
    r"resolved[^.]*\.\s*")

def cost_for_indication(indication: str):
    """Повертає (область, мін, макс) USD на учасника за ключовими словами показання."""
    t = (indication or "").lower()
    for area, (lo, hi, words) in AREA_COSTS.items():
        for w in words:
            if (len(w) <= 4 and re.search(rf"\b{re.escape(w)}\b", t)) or \
                    (len(w) > 4 and w in t):
                return area, lo, hi
    return DEFAULT_COST

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

class FinalDraft(BaseModel):
    recommendation: Literal["Invest", "Conditional", "Do Not Invest"]
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

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def extract_records(data) -> list:
    """Файли evidence — {"evidence": [...]} або просто список записів."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict) and "id" in r]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "id" in v[0]:
                return v
    return []

def load_evidence(folder: Path) -> dict:
    records = {}
    for p in sorted(folder.glob("*.json")):
        for r in extract_records(load_json(p)):
            records[r["id"]] = r
    return records

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

def other_drugs_in(text: str) -> list:
    """Назви препаратів у тексті, яких немає серед імен цільового препарату."""
    return sorted({m.group(0).lower() for m in INN_RE.finditer(text or "")}
                  - {n.lower() for n in DRUG_NAMES})

def mentions_drug(c: dict) -> bool:
    """Чи згадує claim (текст, цитата, заголовок запису) цільовий препарат."""
    if not DRUG_NAMES:
        return True
    t = " ".join([c.get("claim", ""), c.get("quote", ""),
                  c.get("record_title") or ""]).lower()
    return any(nm in t for nm in DRUG_NAMES)

def prepare_claims(claims_raw: list, evidence: dict, loose: dict, prefix: str):
    """Присвоюємо id, перевіряємо evidence_id і цитату (по всьому запису).
    Повертаємо (добрі, відкинуті з причиною)."""
    good, dropped = [], []
    n = 1
    for c in claims_raw:
        eid = c.get("evidence_id")
        rec = evidence.get(eid)
        if rec is None:
            dropped.append({"reason": "evidence_id не існує", "claim": c})
            continue
        if eid not in loose:
            loose[eid] = squash(json.dumps(rec, ensure_ascii=False, indent=2))
        if not quote_ok(c.get("quote", ""), loose[eid]):
            dropped.append({"reason": "цитата не знайдена в записі", "claim": c})
            continue
        is_registry = str(rec.get("source_type", "")).startswith("nct")
        if not is_registry and len((c.get("quote") or "").strip()) < MIN_QUOTE_LEN:
            dropped.append({"reason": "цитата надто коротка", "claim": c})
            continue
        q = c.get("quote") or ""
        if len(q) > 400 and q.count(";") >= 8:
            dropped.append({"reason": "шум: цитата — довгий список назв, а не твердження",
                            "claim": c})
            continue
       
        if INDICATION_WORDS and c.get("stage") == "unmet_need" \
                and rec.get("source_type") in ("pubmed", "epmc_pmc", "epmc_ppr") \
                and not any(w in (c.get("claim", "") + " " + c.get("quote", "")).lower()
                            for w in INDICATION_WORDS):
            dropped.append({"reason": "шум: unmet need не про показання", "claim": c})
            continue
        ctext = c.get("claim", "") + " " + c.get("quote", "")
        
        if str(c.get("evidence_id", "")).endswith("_flow") and \
                c.get("direction") == "contradicts" and \
                NOISE_FLOW_ONE_RE.search(c.get("claim", "")):
            dropped.append({"reason": "шум: поодинокий випадок у когорті без порівняння "
                                      "з контролем", "claim": c})
            continue
        if (c.get("direction") == "neutral" and NOISE_FLOW_RE.search(ctext)) or \
                NOISE_ANY_RE.search(ctext) or (
                c.get("stage") == "unmet_need" and NOISE_UNMET_RE.search(ctext)):
            dropped.append({"reason": "шум: вузька підгрупа/асоціація ризику/"
                                      "критерії доглядальника", "claim": c})
            continue

        rec_nums = numbers(json.dumps(rec, ensure_ascii=False))
        claim_nums = numbers(strip_labels(c.get("claim", "")))
        invented = sorted(claim_nums - rec_nums)
        if invented:
            dropped.append({"reason": f"числа {invented} з claim відсутні в записі",
                            "claim": c})
            continue

        c = dict(c)
        q = c.get("quote", "").rstrip()
        if TRUNC_RE.search(q):

            cut = max(q.rfind(ch) for ch in ";,(")
            q2 = q[:cut].rstrip() if cut > 0 else ""
            if len(q2) >= 30 and quote_ok(q2, loose[eid]):
                c["quote"] = q2
                c["quote_trimmed"] = True
            else:
                dropped.append({"reason": "цитата обірвана на півслові", "claim": c})
                continue

        if LOW_CERT_RE.search(c.get("quote", "")) and c.get("confidence") != "low":
            c["confidence"] = "low"
            c["confidence_adjusted"] = "цитата: low certainty / не рецензовано / від компанії"

        if re.search(r"(?i)doping", rec.get("title") or "") and c.get("confidence") != "low":
            c = dict(c)
            c["confidence"] = "low"
            c["confidence_adjusted"] = "назва запису: антидопінгове дослідження малої вибірки"

        backed = numbers(c.get("quote", "")) | numbers(rec.get("title") or "") | numbers(
            json.dumps(rec.get("meta") or {}, ensure_ascii=False))
        outside = sorted(claim_nums - backed)

        dur = set(re.findall(r"(?i)\b(\d+(?:[.,]\d+)?)\s*[- ]?(?:weeks?|wks?|months?|days?)\b",
                             c.get("claim", "")))
        dur_only = [n for n in outside if n in dur or n.replace(",", ".") in dur]
        if dur_only:
            outside = [n for n in outside if n not in dur_only]
            c = dict(c)
            c["duration_from_record"] = dur_only

        unbacked_key = sorted(percent_numbers(c.get("claim", "")) & set(outside))
        if unbacked_key:
            dropped.append({"reason": f"ключові числа {unbacked_key} є в записі, але "
                                      f"не в цитаті claim", "claim": c})
            continue
        unbacked = [n for n in outside if not YEAR_RE.match(n)]
        if unbacked:
            dropped.append({"reason": f"числа {unbacked} є в записі, але не в цитаті "
                                      f"claim й не в meta", "claim": c})
            continue
        item = dict(c)

        if DRUG_NAMES and rec.get("source_type") in ("pubmed", "epmc_pmc", "epmc_ppr"):
            in_claim = any(nm in c.get("claim", "").lower() for nm in DRUG_NAMES)
            in_quote = any(nm in c.get("quote", "").lower() for nm in DRUG_NAMES)
            item["drug_not_in_quote"] = bool(in_claim and not in_quote)

        if DRUG_NAMES and item.get("stage") in OTHER_DRUG_STAGES \
                and item.get("direction") in ("supports", "contradicts") \
                and not any(nm in item.get("claim", "").lower() for nm in DRUG_NAMES):
            others = other_drugs_in(item.get("claim", ""))
            if others:
                item["reclassified_other_drug"] = others
                item["stage"], item["direction"] = "competition", "neutral"

        if DRUG_NAMES and rec.get("source_type") in ("pubmed", "epmc_pmc", "epmc_ppr") \
                and item.get("direction") in ("supports", "contradicts") \
                and item.get("stage") in ("clinical", "safety_or_failure", "translation") \
                and not any(nm in " ".join([item.get("quote", ""),
                                            rec.get("title") or ""]).lower()
                            for nm in DRUG_NAMES):
            item["reclassified_no_target_drug"] = True
            item["stage"], item["direction"] = "other", "neutral"

        item["numbers_outside_quote"] = [n for n in outside if not YEAR_RE.match(n)]
        item["id"] = f"{prefix}{n:03d}"
        item["source_type"] = rec.get("source_type")
        item["record_title"] = rec.get("title")
        item["url"] = rec.get("url")
        item["is_extra"] = prefix != "C"
        good.append(item)
        n += 1
    return good, dropped

def claims_for_prompt(claims: list) -> str:
    rows = []
    for c in claims:
        rows.append(json.dumps({
            "id": c["id"], "stage": c["stage"], "direction": c["direction"],
            "confidence": c["confidence"], "source_type": c["source_type"],
            "claim": c["claim"],
        }, ensure_ascii=False))
    return "\n".join(rows)

def claim_numbers(claim: dict) -> set:
    return numbers(claim["claim"]) | numbers(claim["quote"])

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

def says_no_human_data(text: str) -> bool:
    return any(r.search(text or "") for r in NO_HUMAN_DATA_RES)

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

def order_rationale(items: list, claim_map: dict) -> list:
    """Рекомендація: спочатку [E] (найсильніший клінічний результат першим), потім [AI]."""
    ev = [x for x in items if x["kind"] == "evidence" and x["claim_ids"]]
    rest = [x for x in items if x not in ev]
    ev.sort(key=lambda x: -max(claim_strength(claim_map[i]) for i in x["claim_ids"]))
    return ev + rest

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

def months_between(a, b) -> float:
    return (b - a).days / 30.4

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

    # --- 1. завантаження і перевірка claims
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
            "gaps": [clean_ids(g) for g in draft.gaps],
        }

    drop_false_absence(sections, claim_map, issues)

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
    final_prompt = (FINAL_TASK
                    + f"\nDRUG: {args.drug}\nINDICATION: {args.indication}\n"
                    + known_names_line(args.drug) + "\n"
                    + "CLAIM COUNTS BY STAGE AND DIRECTION:\n"
                    + json.dumps(counts, ensure_ascii=False)
                    + "\n\nDRAFTED SECTIONS:\n" + "\n".join(sections_text)
                    + "\n\nCONFLICTS:\n" + conflicts_text
                    + "\n\nCAPITAL ESTIMATE:\n" + capital_text
                    + "\n\nALL CONTRADICTING CLAIMS:\n" + claims_for_prompt(contra))
    final = runner.call("final", FINAL_MODEL, final_prompt, FinalDraft)

    rationale = validate_statements(final.recommendation_rationale, claim_map,
                                    "Recommendation", issues, single_evidence=True)

    lead = lead_efficacy_item(claim_map)
    if lead and not any(x["kind"] == "evidence" and lead["claim_ids"][0] in x["claim_ids"]
                        for x in rationale):
        rationale.append(lead)
        issues.append(f"Recommendation: код додав головний результат ефективності "
                      f"{lead['claim_ids'][0]} (модель його не процитувала)")
    rationale = order_rationale(rationale, claim_map)

    recommendation = final.recommendation
    unresolved = [c for c in conflicts if c["status"] == "unresolved"]
    if recommendation == "Invest" and (final.critical_unknowns or unresolved):
        recommendation = "Conditional"
        issues.append("Рекомендацію «Invest» знижено до «Conditional»: "
                      "залишаються критичні невідомі або невирішені суперечності.")

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
        new_ids = [c["id"] for c in claims if c.get("is_extra")]
        print(f"  Нові claims: {', '.join(new_ids) or 'немає'}")
        old_unknowns = set(old.get("critical_unknowns", []))
        for u in final.critical_unknowns:
            if u not in old_unknowns:
                print(f"  + нове критичне невідоме: {u}")

if __name__ == "__main__":
    main()