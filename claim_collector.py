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


folder = Path("./results/raw/")

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
   appear in the provided records.
5. If a record contains nothing useful (no abstract text, no result, only a title), skip it.
   Do not invent claims to fill space.

QUOTES AND NUMBERS:
6. Every claim must include a quote: an exact, word-for-word copy of a fragment from that
   record (max 200 characters). Do not paraphrase inside the quote. Do not fix typos. Copy
   special symbols exactly as written (for example ², ≥, −, ·); never replace them with
   plain characters.
7. The quote must be ONE continuous fragment copied exactly from the record. Never assemble
   a quote from several fields, never use "..." inside a quote, and prefer a full phrase or
   sentence over a bare field name and number like "enrollment": 300.
8. Every number in a claim must appear in the record text. The quote must contain the main
   fact of the claim (what was tested or what was found); it does not have to contain every
   number.

HOW MANY CLAIMS:
9. Clinical trial records: one claim describing the trial (drug, population, comparator,
   primary outcome, and phase, status and enrollment if stated), with the quote taken from
   the title or summary text; plus one claim for the results or for the reason the trial
   stopped, only if the record contains them.
10. Scientific articles and preprints: up to 4 claims. Prefer reported effect sizes with
    numbers, safety findings, and limitations stated by the authors. Skip records with no
    abstract text.
11. Open Targets records: a separate claim for each mechanism of action, each target
    function, and each target-disease association with its evidence types and scores.
12. FDA label and FDA search records: extract what the record states (indications, boxed
    warnings, adverse reactions, or that no label was found). A drug appearing in a text-search
    list is NOT evidence that it is indicated for the condition; state only what the record
    says and do not call such a drug a competitor.
13. Claims from preprints (source_type epmc_ppr) must have confidence "medium" or "low".

CLASSIFICATION:
14. stage, one of:
    - "unmet_need": disease burden, patient population, current standard of care
    - "mechanism": biology of the target or pathway, genetics, animal models
    - "translation": drug exposure, PK/PD, target engagement, biomarkers in humans
    - "clinical": trial design, endpoints, results in patients
    - "competition": other drugs, approved therapies, programs against the same target
    - "regulatory": FDA/EMA status, designations, expanded access, labels
    - "safety_or_failure": adverse events, safety signals, stopped or failed trials
    - "other": anything else
15. direction, one of:
    - "supports": the record reports a positive result for the drug (efficacy, favourable
      safety, strong mechanism evidence)
    - "contradicts": the record reports a negative or cautionary result (failure, early
      termination, safety signal, lack of efficacy, conflicting evidence)
    - "neutral": everything else, including trial design, enrollment, phase, status of an
      ongoing trial and background facts
    A trial being registered, recruiting or large is NOT evidence that the drug works.
    A safety problem or adverse event is "contradicts", not "supports".
16. confidence: "high" if the fact is stated directly with numbers or a clear status,
    otherwise "medium" or "low".

OUTPUT:
17. Respond with JSON only, no markdown, matching the provided schema.

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

with open("./results/claims.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)