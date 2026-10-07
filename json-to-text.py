from google import genai
import os
from pathlib import Path
import dotenv
from pydantic import BaseModel
import json


class Claim(BaseModel):
    claim: str
    evidence_id: str
    quote: str
    stage: str
    direction: str
    confidence: str


class ClaimsResponse(BaseModel):
    claims: list[Claim]


folder = Path("./datagetters/results/")

prompt = """
You are a fact-extraction assistant for biotech investment due diligence.

You receive source records (clinical trial registry entries and scientific articles).
Your only job is to extract factual statements that are explicitly written in these records.

STRICT RULES:

1. Use ONLY information stated in the provided records. Never use outside knowledge.
2. Do NOT draw conclusions, make predictions, or give opinions.
3. One claim = one fact, written as one short sentence.
4. Every claim must cite the id of the record it comes from (evidence_id).
5. Every claim must include a quote: an exact, word-for-word copy of a fragment from that record
   (max 200 characters). Do not paraphrase inside the quote. Do not fix typos.
6. Classify each claim:
   - stage: one of "unmet_need", "mechanism", "translation", "clinical",
     "competition", "safety_or_failure", "other"
   - direction: "supports", "contradicts", or "neutral"
   - confidence: "high", "medium", or "low"
7. Prefer facts that matter for an investment decision:
   trial status and why it stopped, phase, enrollment, primary outcomes,
   reported effect sizes and p-values, safety findings, mechanism evidence.
8. Process EVERY record.
9. Extract all entries from "evidence" block. They contain '"id":' field
10. Do not skip records.
11. Make your output as a JSON. No markdown. 
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

with open("./results/output0.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)