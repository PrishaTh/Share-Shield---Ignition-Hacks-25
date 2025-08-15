import re
from typing import List
from src.schema import Finding, Findings

RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")
RE_PHONE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b")
RE_CC    = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
# add Luhn check to reduce FPs
def _luhn_ok(s: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D","",s)]
    if not (13 <= len(digits) <= 19): return False
    checksum = 0
    reverse = digits[::-1]
    for i, d in enumerate(reverse):
        if i % 2 == 1:
            d *= 2
            if d > 9: d -= 9
        checksum += d
    return checksum % 10 == 0

def run_fallback(text: str) -> Findings:
    out: List[Finding] = []
    for m in RE_EMAIL.finditer(text):
        out.append(Finding(kind="email", start=m.start(), end=m.end(),
                           value_preview=m.group()[:2]+"***", confidence=0.85, reason="regex"))
    for m in RE_PHONE.finditer(text):
        out.append(Finding(kind="phone_number", start=m.start(), end=m.end(),
                           value_preview="***"+m.group()[-4:], confidence=0.6, reason="regex"))
    for m in RE_CC.finditer(text):
        if _luhn_ok(m.group()):
            out.append(Finding(kind="credit_card", start=m.start(), end=m.end(),
                               value_preview="**** **** **** "+re.sub(r'\D','',m.group())[-4:],
                               confidence=0.9, reason="regex+luhn"))
    return Findings(findings=out)
