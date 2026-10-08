"""
build_report.py — збирає Investment Underwriting Report із claims.

Конвеєр:
  results/claims.json + results/evidence/*.json
    -> перевірка цитат кодом (та сама логіка, що в check_claims.py: цитата шукається
       в УСЬОМУ записі — title, text, meta — з нормалізацією спецсимволів)
    -> 6 етапних викликів LLM (наука, трансляція, клінічний план, конкуренти,
       комерція, ризики)
    -> виклик «суперечності»: пари supports / contradicts по одній темі
    -> капітал рахує КОД за реєстром: Phase 3 зі статусом RECRUITING / NOT_YET_RECRUITING,
       без результатів; розмір вибірки з реєстру; вартість за учасника — припущення
    -> фінальна збірка (рекомендація, невідоме, питання до діліджансу)
    -> джерела підставляє КОД за id claims (модель джерела не вигадує)
    -> results/report.json (повний ланцюг для drill-down) + report.md (тіло звіту)
       + report_claims.md (додаток з усіма claims і цитатами)
    -> results/dropped_claims.json (які claims відкинуто і чому)
    -> results/run_log.jsonl (токени, час, вартість кожного виклику)

Запуск:
  python build_report.py
  python build_report.py --drug retatrutide --indication obesity
  python build_report.py --extra extra_claims.json --out-prefix report_new \
        --compare results/report.json          # демо: нові докази змінюють висновок
"""

import argparse
import json
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

# ---------------------------------------------------------------- налаштування

MODEL = "gemini-3.1-flash-lite"       # модель для етапних викликів
FINAL_MODEL = "gemini-3.1-flash-lite"  # можна поставити сильнішу для фінальної збірки
MAX_RETRIES = 3

# Ціна за 1 млн токенів (USD). ЗАГЛУШКИ — перевір актуальні ціни на сторінці
# цін Gemini API і впиши свої, інакше cost у логу буде неточним.
PRICE_IN_PER_M = 0.10
PRICE_OUT_PER_M = 0.40

# ПРИПУЩЕННЯ (не з джерел!): вартість клінічного випробування на одного учасника, USD.
# Це діапазон для грубої оцінки; змінюй у конфігу і вказуй у презентації як припущення.
COST_PER_PARTICIPANT_LOW = 15_000
COST_PER_PARTICIPANT_HIGH = 50_000

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


# ---------------------------------------------------------------- схеми відповідей

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


# ---------------------------------------------------------------- промпти

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
3. critical_unknowns: facts that, if known, would change the recommendation. Concrete.
4. diligence_questions: 5 to 10 questions a diligence team should ask the company or
   check in data. Each must be specific and answerable.
5. what_would_change_the_conclusion: concrete new evidence that would move the
   recommendation up or down (for example a specific kind of trial result).
6. Use only the facts in the sections and claims. Cite claim ids exactly as given.
"""


# ---------------------------------------------------------------- допоміжні функції
# Функції squash / quote_ok / canon / numbers — копія логіки з check_claims.py,
# щоб звіт відкидав рівно ті цитати, які б відкинула й перевірка.

def squash(text: str) -> str:
    """Лояльне порівняння: m² -> m2, потім лишаємо лише літери й цифри."""
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\W_]+", "", text)


def quote_ok(quote: str, target_squashed: str) -> bool:
    """Цитата перевірена, якщо кожен її шматок є в записі. Розділювачі шматків:
    '...' та маркер пункту списку '*'. Шматки коротші за 8 символів ігноруємо."""
    pieces = [p for p in re.split(r"\.{3}|…|(?:^|\s)\*\s", quote)
              if len(squash(p)) >= 8]
    return bool(pieces) and all(squash(p) in target_squashed for p in pieces)


def canon(n: str) -> str:
    """30.0 -> 30, 27.50 -> 27.5."""
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def numbers(text: str) -> set:
    """Числа з тексту: десяткові або від двох цифр. NCT-номери ігноруємо,
    розділювачі тисяч прибираємо, '·' як десяткову крапку приводимо до '.'."""
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"NCT\d+", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    found = (canon(n.replace("·", ".")) for n in re.findall(r"\d+(?:[.·]\d+)?", text))
    return {n for n in found if "." in n or len(n) >= 2}


def strip_labels(text: str) -> str:
    """Перед перевіркою чисел прибираємо те, що числами фактів не є:
    id claims (C013) та назви фаз (Phase 3, Phase 3b)."""
    text = re.sub(r"\b[CX]\d{3}\b", " ", text)
    text = re.sub(r"(?i)\bphase\s*\d+\w*", " ", text)
    return text


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


# ---------------------------------------------------------------- виклик LLM

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
            except Exception as e:  # мережа, квота, невалідний JSON
                last_err = e
                print(f"  [{step}] спроба {attempt} не вдалась: {e}")
                time.sleep(2 * attempt)
        raise RuntimeError(f"Крок {step} не вдався після {MAX_RETRIES} спроб: "
                           f"{last_err}")


# ---------------------------------------------------------------- claims

TRUNC_RE = re.compile(r"(?:[;,(=<>±:]|\s[a-z])$")
LOW_CERT_RE = re.compile(r"(?i)\b(?:very )?low[- ](?:certainty|quality)\b")
YEAR_RE = re.compile(r"^(?:19|20|21)\d\d$")


def percent_numbers(text: str) -> set:
    """Числа, після яких стоїть % (ключові факти, не роки й не номери)."""
    text = unicodedata.normalize("NFKC", strip_labels(text or ""))
    return {canon(n.replace("·", ".")) for n in
            re.findall(r"(\d+(?:[.·]\d+)?)\s*%", text)}


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
        # числа з тексту claim мають бути в записі: якщо їх немає ніде — вигадані
        rec_nums = numbers(json.dumps(rec, ensure_ascii=False))
        claim_nums = numbers(strip_labels(c.get("claim", "")))
        invented = sorted(claim_nums - rec_nums)
        if invented:
            dropped.append({"reason": f"числа {invented} з claim відсутні в записі",
                            "claim": c})
            continue
        # цитата обірвана (закінчується на розділовому знаку чи одній малій літері)
        c = dict(c)
        q = c.get("quote", "").rstrip()
        if TRUNC_RE.search(q):
            # пробуємо відрізати обірваний хвіст по останньому ; , ( і перевірити знову
            cut = max(q.rfind(ch) for ch in ";,(")
            q2 = q[:cut].rstrip() if cut > 0 else ""
            if len(q2) >= 30 and quote_ok(q2, loose[eid]):
                c["quote"] = q2
                c["quote_trimmed"] = True
            else:
                dropped.append({"reason": "цитата обірвана на півслові", "claim": c})
                continue
        # якщо сама цитата каже «low certainty», впевненість не може бути вищою
        if LOW_CERT_RE.search(c.get("quote", "")) and c.get("confidence") != "low":
            c["confidence"] = "low"
            c["confidence_adjusted"] = "цитата містить low certainty"
        # є в записі, але не в цитаті і не в meta
        backed = numbers(c.get("quote", "")) | numbers(
            json.dumps(rec.get("meta") or {}, ensure_ascii=False))
        outside = sorted(claim_nums - backed)
        # ключові числа (відсотки) без опори в цитаті — claim відкидаємо
        unbacked_key = sorted(percent_numbers(c.get("claim", "")) & set(outside))
        if unbacked_key:
            dropped.append({"reason": f"ключові числа {unbacked_key} є в записі, але "
                                      f"не в цитаті claim", "claim": c})
            continue
        item = dict(c)
        # роки у флаг не виносимо: це шум (діапазони років з контексту запису)
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


# ---------------------------------------------------------------- перевірка чернеток

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
        if s.kind == "evidence":
            if not ids:
                issues.append(f"{section}: evidence без claims відкинуто: "
                              f"{s.text[:70]}")
                continue
            families = {claim_map[i]["stage"] in MECH_STAGES for i in ids}
            dirs = {claim_map[i]["direction"] for i in ids}
            reason = None
            if len(families) > 1:
                reason = "поєднує біологію/PK і клінічні дані"
            elif {"supports", "contradicts"} <= dirs:
                reason = "поєднує claims із протилежними напрямками"
            elif single_evidence and len(ids) > 1:
                reason = "у рекомендації факт має спиратися на один claim"
            elif single_evidence and any(
                    claim_map[i].get("confidence") == "low"
                    or claim_map[i].get("source_type") == "epmc_ppr" for i in ids):
                reason = "у рекомендації не можна подавати low-confidence/препринт як факт"
            if not reason and single_evidence and len(ids) == 1:
                # у рекомендації [E] = дослівно текст одного claim, без домислів моделі
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
                    # у рекомендації число поза цитованим claim = не факт, а висновок
                    item["kind"] = "inference"
                    issues.append(f"{section}: [E] знижено до [AI] — числа {missing} "
                                  f"відсутні в цитованому claim: {s.text[:70]}")
                elif missing:
                    item["unverified_numbers"] = missing
                    issues.append(f"{section}: числа {missing} відсутні в цитованих "
                                  f"claims: {s.text[:70]}")
        out.append(item)
    return out


PLACEBO_RE = re.compile(r"(?i)\bplacebo\b|control group|control arm|\bcontrols?\b")
ACTIVE_RE = re.compile(r"(?i)other (?:incretin|glp|treatment|therap|drug|agent)|"
                       r"tirzepatide|semaglutide|dulaglutide|liraglutide|"
                       r"active comparator|danuglipron")


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
        out.append({"topic": c.topic, "endpoint": c.endpoint,
                    "shared_comparator": c.shared_comparator,
                    "supporting": sup, "contradicting": con,
                    "assessment": c.assessment, "status": c.status})
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


def find_key(obj, names):
    """Рекурсивно шукає перше непорожнє значення за одним із ключів (регістр і «_»
    ігноруються). Потрібно, бо meta у записів із різних джерел має різний вигляд."""
    want = {n.lower().replace("_", "") for n in names}
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                if str(k).lower().replace("_", "") in want and v not in (None, "", []):
                    return v
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def norm_status(v) -> str:
    return re.sub(r"[^A-Z]+", "_", str(v).upper()).strip("_") if v else ""


def norm_phase3(v) -> bool:
    """Phase 3 або Phase 2/Phase 3."""
    if not v:
        return False
    s = re.sub(r"[^A-Z0-9]", "", json.dumps(v, ensure_ascii=False).upper())
    return "PHASE3" in s


def norm_int(v):
    if isinstance(v, dict):
        v = v.get("count")
    try:
        n = int(float(str(v).replace(",", "").replace(" ", "")))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def trial_table(evidence: dict) -> dict:
    """Збираємо випробування з основних записів реєстру (nct, nct_aact), зливаючи
    дублі за NCT-номером. Фаза, статус і розмір вибірки беруться з реєстру, а не з
    тексту моделі."""
    recs = [r for r in evidence.values()
            if r.get("source_type") in ("nct", "nct_aact")]
    recs.sort(key=lambda r: r.get("source_type") != "nct_aact")  # AACT першим
    table = {}
    for r in recs:
        m = re.search(r"NCT\d{8}", " ".join(str(r.get(k) or "")
                                            for k in ("id", "url", "title")))
        if not m:
            continue
        t = table.setdefault(m.group(0), {
            "nct": m.group(0), "evidence_ids": [], "title": None, "status": "",
            "phase3": None, "enrollment": None, "has_results": None, "blob": ""})
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
        hr = find_key(meta, ["has_results", "hasResults"])
        if t["has_results"] is None and hr is not None:
            t["has_results"] = str(hr).lower() in ("true", "1", "yes")
    return table


ENROLLING = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}


def capital_from_registry(evidence: dict, claims: list, claim_map: dict,
                          issues: list, drug: str, indication: str):
    """Капітал до наступної віхи — ДЕТЕРМІНОВАНО, за статусом у реєстрі:
      - рахуємо Phase 3, що набирають учасників (RECRUITING / NOT_YET_RECRUITING /
        ENROLLING_BY_INVITATION) і ще без результатів;
      - набір закрито (ACTIVE_NOT_RECRUITING), завершені, із результатами чи
        опубліковані в літературі — не рахуємо, лише перелічуємо;
      - розмір вибірки — з реєстру; суму і вартість рахує код."""
    table = trial_table(evidence)
    reported = reported_trials(claims, evidence)
    counted, closed, done = [], [], []
    other = []  # залишено порожнім: фільтр за показанням прибрано (надто грубий)
    for nct, t in sorted(table.items()):
        if not t["phase3"]:
            if t["phase3"] is None:
                issues.append(f"Capital: {nct} пропущено — фаза в реєстрі не вказана")
            continue  # Phase 1/2 до подачі досьє не потрібні
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
    for t in counted:
        stmts.append({
            "text": f"{t['nct']} ({short(t)}): Phase 3, registry status "
                    f"{t['status']}, {t['enrollment']:,} participants planned. "
                    f"Counted: still enrolling.",
            "kind": "evidence", "claim_ids": claim_ids_of(t),
            "evidence_ids": t["evidence_ids"], "unverified_numbers": []})
    if closed:
        stmts.append({
            "text": "Phase 3 trials with enrollment closed (ACTIVE_NOT_RECRUITING), "
                    "not counted because most of their cost is already incurred: "
                    + "; ".join(f"{t['nct']}"
                                + (f" ({t['enrollment']:,})" if t["enrollment"] else "")
                                for t in closed) + ".",
            "kind": "evidence", "claim_ids": [],
            "evidence_ids": [e for t in closed for e in t["evidence_ids"]],
            "unverified_numbers": []})
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

    total = sum(t["enrollment"] for t in counted)
    calc = None
    if total > 0:
        low, high = total * COST_PER_PARTICIPANT_LOW, total * COST_PER_PARTICIPANT_HIGH
        calc = {"participants_total": total,
                "trials_counted": [t["nct"] for t in counted],
                "trials_enrollment_closed": [t["nct"] for t in closed],
                "trials_excluded_done": [t["nct"] for t in done],
                "cost_per_participant_low": COST_PER_PARTICIPANT_LOW,
                "cost_per_participant_high": COST_PER_PARTICIPANT_HIGH,
                "usd_low": low, "usd_high": high}
        stmts.append({
            "text": f"AI inference with an ASSUMPTION that is not from the sources: "
                    f"{total:,} participants x ${COST_PER_PARTICIPANT_LOW:,}-"
                    f"${COST_PER_PARTICIPANT_HIGH:,} per participant = about "
                    f"${low / 1e6:,.0f}M-${high / 1e6:,.0f}M for the counted trials "
                    f"only (excludes manufacturing, regulatory filing and launch).",
            "kind": "inference",
            "claim_ids": sorted({i for t in counted for i in claim_ids_of(t)}),
            "evidence_ids": [e for t in counted for e in t["evidence_ids"]],
            "unverified_numbers": []})
    else:
        stmts.append({"text": "No Phase 3 trial is still enrolling, so the new-enrollment "
                              "cost is about zero; the remaining spend cannot be "
                              "computed from the registry (it has no cost or "
                              "progress data), see the upper bound below.",
                      "kind": "inference", "claim_ids": [], "evidence_ids": [],
                      "unverified_numbers": []})
    closed_total = sum(t["enrollment"] or 0 for t in closed)
    if closed_total > 0:
        outc = [t for t in closed if re.search(r"event-driven|major adverse",
                                               t["blob"])]
        rest = [t for t in closed if t not in outc]
        outc_n = sum(t["enrollment"] or 0 for t in outc)
        rest_n = closed_total - outc_n
        lo, hi = (closed_total * COST_PER_PARTICIPANT_LOW,
                  closed_total * COST_PER_PARTICIPANT_HIGH)
        r_lo, r_hi = (rest_n * COST_PER_PARTICIPANT_LOW,
                      rest_n * COST_PER_PARTICIPANT_HIGH)
        if calc is None:
            calc = {"participants_total": 0}
        calc["closed_upper_bound_usd"] = [lo, hi]
        calc["closed_without_outcomes_trials_usd"] = [r_lo, r_hi]
        calc["outcomes_trials"] = [t["nct"] for t in outc]
        text = (f"For reference only (AI inference with the same ASSUMPTION): the "
                f"full cost of the {len(closed)} Phase 3 trials with closed enrollment "
                f"({closed_total:,} participants) would be about "
                f"${lo / 1e6:,.0f}M-${hi / 1e6:,.0f}M. This is an UPPER BOUND on their "
                f"remaining spend, because most of it is already incurred.")
        if outc and rest:
            text += (f" Event-driven outcomes trial(s) "
                     f"{', '.join(t['nct'] for t in outc)} ({outc_n:,} participants) "
                     f"are included in this; without them the figure is about "
                     f"${r_lo / 1e6:,.0f}M-${r_hi / 1e6:,.0f}M ({rest_n:,} "
                     f"participants).")
        stmts.append({"text": text, "kind": "inference", "claim_ids": [],
                      "evidence_ids": [e for t in closed for e in t["evidence_ids"]],
                      "unverified_numbers": []})
    for note in ("Trial status and enrollment are a snapshot of the registry at "
                 "the time of the search.",
                 "Cost per participant is a flat assumption; real costs differ by "
                 "trial design, country and duration."):
        stmts.append({"text": f"Limit of the estimate: {note}", "kind": "inference",
                      "claim_ids": [], "evidence_ids": [], "unverified_numbers": []})
    return stmts, calc


# ---------------------------------------------------------------- рендер

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
                    if c.get("numbers_outside_quote") else ""))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- головна логіка

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

    # --- 2. етапні виклики
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
                  + f"\n\nDRUG: {args.drug}\nINDICATION: {args.indication}\n\n"
                  + "CLAIMS (one JSON per line):\n" + claims_for_prompt(sel))
        draft = runner.call(spec["key"], MODEL, prompt, SectionDraft)
        sections[spec["key"]] = {
            "title": spec["title"],
            "statements": validate_statements(draft.statements, claim_map,
                                              spec["title"], issues),
            "gaps": draft.gaps,
        }

    # --- 3. суперечності та капітал
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

    # --- 4. фінальна збірка
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
                    + f"\nDRUG: {args.drug}\nINDICATION: {args.indication}\n\n"
                    + "CLAIM COUNTS BY STAGE AND DIRECTION:\n"
                    + json.dumps(counts, ensure_ascii=False)
                    + "\n\nDRAFTED SECTIONS:\n" + "\n".join(sections_text)
                    + "\n\nCONFLICTS:\n" + conflicts_text
                    + "\n\nCAPITAL ESTIMATE:\n" + capital_text
                    + "\n\nALL CONTRADICTING CLAIMS:\n" + claims_for_prompt(contra))
    final = runner.call("final", FINAL_MODEL, final_prompt, FinalDraft)

    rationale = validate_statements(final.recommendation_rationale, claim_map,
                                    "Recommendation", issues, single_evidence=True)

    recommendation = final.recommendation
    unresolved = [c for c in conflicts if c["status"] == "unresolved"]
    if recommendation == "Invest" and (final.critical_unknowns or unresolved):
        recommendation = "Conditional"
        issues.append("Рекомендацію «Invest» знижено до «Conditional»: "
                      "залишаються критичні невідомі або невирішені суперечності.")

    # --- 5. джерела підставляє код
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

    # --- порівняння з попереднім звітом (демо «нові докази змінили висновок»)
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