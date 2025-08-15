import json, os
from typing import List
from pydantic import BaseModel
from google import genai
from google.genai import types
from src.schema import Finding, Findings

SYSTEM_INSTRUCTIONS = """You are a security DLP classifier.
Given plain text from an OCR pass, identify sensitive data and return spans.
Rules:
- Return ONLY JSON via the provided schema.
- Prefer high precision; do not hallucinate spans not present in text.
- Detect: api keys, tokens, JWTs, passwords, private key blocks, AWS keys, OAuth/Bearer tokens,
  credit cards (Luhn), IBAN, bank acct & routing numbers, SWIFT/BIC, emails, phones, IPs, addresses,
  national IDs (e.g., SSN/SIN), URLs that contain tokens.
- For value_preview, mask most of the value (e.g., last 4).
- confidence in [0,1]; reason should be brief (regex hit, checksum, format+context, etc.).
"""

class _FindingsPyd(BaseModel):
    findings: List[Finding]

def detect_with_gemini(text: str) -> Findings:
    client = genai.Client(  # picks GEMINI_API_KEY automatically if set
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    ) if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else genai.Client()

    prompt = f"{SYSTEM_INSTRUCTIONS}\n\nTEXT START\n{text}\nTEXT END"

    # Ask Gemini for JSON matching our Pydantic schema
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_FindingsPyd,
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            max_output_tokens=2048,
        ),
    )

    # Either use parsed or fallback to JSON text
    if getattr(resp, "parsed", None):
        return Findings.model_validate(resp.parsed.model_dump())
    return Findings.model_validate_json(resp.text)
