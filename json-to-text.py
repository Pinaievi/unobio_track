from google import genai
import os
from pathlib import Path
import dotenv

folder = Path("./datagetters/results/")

prompt = """
You are a fact-extraction assistant for biotech investment due diligence.

You receive several source records (clinical trial registry entries and scientific articles).
Your only job is to extract factual statements that are explicitly written in these records.

STRICT RULES:
1. Use ONLY information stated in the provided records. Never use outside knowledge.
2. Do NOT draw conclusions, make predictions, or give opinions.
3. One claim = one fact, written as one short sentence.
4. Every claim must cite the id of the record it comes from (evidence_id).
5. Every claim must include a quote: an exact, word-for-word copy of a fragment from that record
   (max 200 characters). Do not paraphrase inside the quote. Do not fix typos.
6. Classify each claim:
   - stage: one of "unmet_need", "mechanism", "translation", "clinical", "competition", "safety_or_failure", "other"
   - direction: how the fact bears on the drug's prospects: "supports", "contradicts", or "neutral"
     (a stopped trial, a safety problem, or a negative result is "contradicts")
   - confidence: "high" if the fact is stated directly with numbers or clear status, otherwise "medium" or "low"
7. If a record contains nothing useful, skip it. Do not invent claims to fill space.
8. Prefer facts that matter for an investment decision: trial status and why it stopped, phase, enrollment,
   primary outcomes, reported effect sizes and p-values, safety findings, mechanism evidence.

"""

dotenv.load_dotenv()
key = os.environ["API_KEY"]

client = genai.Client(api_key=key)

statements = ""

for path in folder.glob("*.json"):
    json_text = None

    print(str(path))
    
    with open(path, "r", encoding="utf-8") as f:
        json_text = f.read()

    interaction = client.interactions.create(
        model="gemini-3.1-flash-lite",
        input=[
            {
                "type": "text",
                "text": f"{prompt}\n\nJSON:\n{json_text}"
            }
        ]
    )

    print(interaction.output_text)
    statements += interaction.output_text