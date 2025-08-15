from typing import Optional
from src.sanitizer import pre_scrub
from src.detectors.fallback_regex import run_fallback
from src.detectors.gemini_detector import detect_with_gemini
from src.schema import Findings, Finding

def classify_text(text: str, privacy_first: bool = True, use_fallback: bool = True) -> Findings:
    scrubbed = text
    if privacy_first:
        scrubbed, _ = pre_scrub(text)  # mask blatant secrets before sending upstream

    # First pass: fast regex to catch obvious items 
    base = run_fallback(scrubbed) if use_fallback else Findings(findings=[])

    # Second pass: LLM classification to add kinds, spans, dedupe/confirm
    llm = detect_with_gemini(scrubbed)

    # naive merge by overlapping spans + kind
    merged = base.findings[:]
    for f in llm.findings:
        if not any((f.kind == g.kind and abs(f.start - g.start) < 2 and abs(f.end - g.end) < 2) for g in merged):
            merged.append(f)

    # sort by start
    merged.sort(key=lambda f: (f.start, f.end))
    return Findings(findings=merged)
