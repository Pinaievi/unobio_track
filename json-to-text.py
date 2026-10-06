from google import genai
import os
from pathlib import Path
import dotenv


dotenv.load_dotenv()

key = os.environ["API_KEY"]

client = genai.Client(api_key=key)

file = client.files.upload(file=r"D:\\evidence_raw.json")

prompt = """
Parse this file in the following format. In the end, add ALL URL's written in provided file. No markdown.

Recommendation: Invest / Conditional / Do Not Invest
Scientific thesis
Human translation thesis
Clinical development plan
Competitive landscape
Commercial opportunity
Capital required to reach the next major milestone
Key risks and failure modes
Critical unknowns
5 to 10 highest-value diligence questions
Sources supporting major claims
"""

interaction = client.interactions.create(
    model="gemini-3.1-flash-lite",
    input=[
        {
            "type": "text",
            "text": prompt,
        },
        {
            "type": "document",
            "uri": file.uri,
            "mime_type": file.mime_type,
        },
    ],
)


print(interaction.output_text)