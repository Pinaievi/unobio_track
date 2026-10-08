from google import genai
import os
from pathlib import Path
import dotenv
import json
from typing import Literal
from pydantic import BaseModel, Field

class Claim(BaseModel):
    claim: str
    evidence_id: str
    quote: str = Field(description="One continuous fragment copied exactly from the record. "
                                   "No '...' inside.")
    stage: Literal["unmet_need", "mechanism", "translation", "clinical",
                   "competition", "regulatory", "safety_or_failure", "other"]
    direction: Literal["supports", "contradicts", "neutral"] = Field(
        description="supports: positive result for the drug. contradicts: negative or "
                    "cautionary result (failure, early stop, safety signal, no efficacy). "
                    "neutral: design, enrollment, phase, status, background."
    )
    confidence: Literal["high", "medium", "low"]


class ClaimsResponse(BaseModel):
    claims: list[Claim]

folder = Path("./results/evidence/")
output_file = Path("./results/claims.json")

prompt = """
You are a fact-extraction assistant for biotech investment due diligence.

You receive source records (clinical trial registry entries, scientific articles, database
profiles). Your only job is to extract factual statements that are explicitly written in
these records.

GENERAL RULES:
1. Use ONLY information stated in the provided records. Never use outside knowledge.
2. Do NOT draw conclusions, make predictions, or give opinions.
3. One claim = one fact, written as one short sentence.
4. Every claim must cite the id of the record it comes from (evidence_id). Use only ids that
   appear in the provided records. A claim may use ONLY facts written in that single record:
   never combine facts from different records, even if they describe the same trial (for
   example, age limits are in the "nct_aact_population" record, not in the main trial
   record).
5. If a record contains nothing useful (no abstract text, no result, only a title), skip it.
   Do not invent claims to fill space.

QUOTES AND NUMBERS:
6. Every claim must include a quote: an exact, word-for-word copy of a fragment from that
   record. A quote should be under 200 characters and must never exceed 300 characters; if
   the supporting text is longer, quote its most informative part. Do not paraphrase inside the quote. Do not fix typos.
   Copy special symbols exactly as written (for example ², ≥, −, ·); never replace them with
   plain characters.
7. The quote must be ONE continuous fragment copied exactly from the record. Never assemble
   a quote from several fields, never use "..." inside a quote, and prefer a full phrase or
   sentence over a bare field name and number like "enrollment": 300. A quote is never a
   single word or a bare number (for example "Placebo" or "32"): choose a phrase with enough
   context to show what the fact is. Never build a quote by joining values from different
   fields of the record (for example a statistic, its p-value and its confidence interval);
   if the record holds such values only as separate fields, quote the outcome title or a
   summary sentence instead.
8. Records with source_type "nct_aact_population" list eligibility criteria as bullet items
   starting with "*". A quote must be ONE single bullet item, never several items joined
   together. If a claim summarizes several criteria, quote the most important single one.
9. Records with source_type "nct_aact_flow" and "nct_aact_pk" list values group by group.
   Quote the entry of ONE group only (for example "Group A 12 mg: Lost to Follow-up (4),
   Adverse Event (2)").
10. Every number and threshold in a claim (for example a BMI limit) must be written in the
    record text. The quote must contain the main fact of the claim (what was tested or what
    was found); it does not have to contain every number. If the record does not state a
    threshold, do not state it, even if you know it from elsewhere.
11. For human pharmacokinetic data from a small or uncontrolled study (for example a few
    self-administering users, or a drug of unverified origin), state the sample size in the
    claim and use confidence "low". Data on approved drugs of the same class is an analogue,
    not data on the studied drug: say so in the claim.

HOW MANY CLAIMS (by record type):
12. Main clinical trial records (source_type "nct" or "nct_aact"): one claim describing the
    trial (drug, population, comparator, primary outcome, and phase, status and enrollment if
    stated), with the quote taken from the title or summary text; plus one claim for the
    reason the trial stopped, only if the record states it. If the text contains a part
    starting with "Primary outcome results:", extract up to 3 claims from it, one per
    reported comparison or dose group, each with its effect size, confidence interval and
    p-value as written, and take the quote from that part of the text.
13. Competition from trial records: if a main trial record shows that the studied drug is
    compared with another drug (a comparator arm or a head-to-head design), extract one
    claim naming the comparator, with stage "competition" and direction "neutral".
14. Records with source_type "nct_aact_population": up to 3 claims: (a) who is enrolled
    (population, age range, sex, and baseline values such as mean age, BMI or HbA1c if
    stated), stage "unmet_need"; (b) the key inclusion threshold, stage "clinical"; (c) the
    key exclusion, stage "clinical". Direction "neutral". Take the quote from the record's
    text field.
15. Records with source_type "nct_aact_flow": one claim on how many participants started and
    completed in a group (stage "clinical"), and one claim on the main reasons for not
    completing (stage "safety_or_failure"; direction "contradicts" if the main reason is
    adverse events, otherwise "neutral"). Take the quote from the record's text field.
16. Records with source_type "nct_aact_pk": one claim per reported pharmacokinetic parameter
    (Cmax, AUC, half-life, concentration) stating the value, unit and group. Stage
    "translation", direction "neutral". Take the quote from the record's text field.
17. Scientific articles and preprints: up to 4 claims. Prefer reported effect sizes with
    numbers, safety findings, and limitations stated by the authors. Skip records with no
    abstract text.
18. Use how the article was found (meta.found_by_all):
    - if it includes "pk_search" or "tissue_search": extract pharmacokinetic parameters
      (half-life, Cmax, AUC, exposure), exposure-response findings, tissue distribution and
      target engagement results as separate claims with stage "translation";
    - if it includes "epidemiology_search": extract prevalence, incidence and burden figures
      with the year and the population they refer to, stage "unmet_need", direction
      "neutral";
    - results from animals or cells must have confidence "medium" or "low", and the claim
      must say that they are not human data;
    - the way an article was found does not decide the stage: use stage "translation" only
      for exposure, tissue distribution, PK/PD or target engagement; use stage "mechanism"
      for pathway activity and other biology in cells or animals; use stage "clinical" for
      efficacy or safety results in patients.
19. Case reports and safety signals are useful: if a record describes an adverse event or a
    complication in a patient or user, extract one claim stating that it is a single case,
    with stage "safety_or_failure", direction "contradicts" and confidence "low".
20. Open Targets records: a separate claim for each mechanism of action, each target
    function, and each target-disease association with its evidence types and scores.
    Association scores measure the strength of evidence, not the probability of clinical
    success; never describe them as a chance of success. If a target record states that none
    of the top associated diseases matched the indication, extract it as one claim with
    stage "mechanism", direction "neutral", confidence "low", and say that it refers only to
    the top of the list.
21. FDA label and FDA search records: extract what the record states (indications, boxed
    warnings, adverse reactions, or that no label was found). A drug appearing in a
    text-search list is NOT evidence that it is indicated for the condition; state only what
    the record says and do not call such a drug a competitor.
22. FDA adverse event (FAERS) records: one claim on the number of reports and serious
    reports, and one claim on the most frequent reactions. The claim must say that the
    reports are spontaneous and do not prove that the drug caused the events. Stage
    "safety_or_failure", direction "neutral".
23. Claims from preprints (source_type epmc_ppr) must have confidence "medium" or "low".

CLASSIFICATION:
24. stage, one of:
    - "unmet_need": disease burden, patient population, current standard of care
    - "mechanism": biology of the target or pathway, genetics, animal models
    - "translation": drug exposure, PK/PD, target engagement, biomarkers in humans
    - "clinical": trial design, endpoints, results in patients
    - "competition": other drugs, approved therapies, programs against the same target
    - "regulatory": FDA/EMA status, designations, expanded access, labels
    - "safety_or_failure": adverse events, safety signals, stopped or failed trials
    - "other": anything else
25. direction, one of:
    - "supports": the record reports a positive result for the drug (efficacy, favourable
      safety, strong mechanism evidence)
    - "contradicts": the record reports a negative or cautionary result (failure, early
      termination, safety signal, lack of efficacy, conflicting evidence)
    - "neutral": everything else, including trial design, enrollment, phase, status of an
      ongoing trial and background facts
    A trial being registered, recruiting or large is NOT evidence that the drug works.
    A safety problem or adverse event is "contradicts", not "supports".
26. confidence: "high" if the fact is stated directly with numbers or a clear status,
    otherwise "medium" or "low".

OUTPUT:
27. Respond with JSON only, no markdown, matching the provided schema.

"""

dotenv.load_dotenv()
key = os.environ["API_KEY"]

client = genai.Client(api_key=key)

all_claims = []

for path in folder.glob("*.json"):
    print(str(path))

    file = client.files.upload(file=path)

    interaction = client.interactions.create(
        model="gemini-3.1-flash-lite",
        input=[
            {
                "type": "text",
                "text": prompt
            },
            {
                "type": "document",
                "uri": file.uri,
                "mime_type": file.mime_type,
            },
        ],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ClaimsResponse.model_json_schema(),
        },
    )
    
    response = interaction.output_text
    
    print(response)
    data = json.loads(response)

    all_claims.extend(data["claims"])

result = {
    "claims": all_claims
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)