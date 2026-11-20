"""Input screening and output scrubbing for the helpdesk agent."""
from __future__ import annotations

import re

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"disregard (the )?(system|developer) (prompt|message|instructions)",
    r"(print|show|reveal|repeat|output) (me )?(your|the) (system|initial|hidden) prompt",
    r"you are now (dan|developer mode|unrestricted|jailbroken)",
    r"act as (an? )?(unrestricted|unfiltered|evil)",
    r"reveal (the )?(admin|root|service) (password|credentials?|api key)",
    r"begin (admin|developer) mode",
]

SCOPE_TERMS = {
    "leave", "vacation", "annual", "sick", "casual", "holiday", "attendance", "accrual",
    "expense", "reimbursement", "per diem", "travel", "claim", "receipt", "cab", "hotel",
    "it", "laptop", "vpn", "password", "mfa", "software", "install", "device", "usb",
    "security", "phishing", "incident", "access", "badge", "onboarding", "probation",
    "hr", "payroll", "helpdesk", "policy", "employee", "manager", "job", "account",
    "email", "jira", "confluence", "github", "portal", "compensatory", "encashment",
    "certificate", "finance", "approval", "buddy", "standup", "confirmation",
}

EMPLOYEE_ID_RE = re.compile(r"\bE\d{3}\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")
AADHAAR_RE = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
CARD_RE = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b")


def check_query(query: str) -> dict:
    text = query.strip().lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return {"allowed": False, "kind": "injection", "reason": f"matched: {pattern}"}
    if EMPLOYEE_ID_RE.search(query):
        return {"allowed": True, "kind": "employee"}
    words = set(re.findall(r"[a-z]+", text))
    if words & SCOPE_TERMS or "per diem" in text:
        return {"allowed": True, "kind": "policy"}
    return {"allowed": False, "kind": "out_of_scope", "reason": "no HR/IT intent detected"}


def redact(text: str) -> tuple[str, list[str]]:
    hits = []

    def _sub(regex, label, keep_internal=False):
        nonlocal text

        def repl(m):
            value = m.group(0)
            if keep_internal and value.endswith("@company.example"):
                return value
            hits.append(label)
            return f"[{label} redacted]"

        text = regex.sub(repl, text)

    _sub(EMAIL_RE, "email", keep_internal=True)
    _sub(PHONE_RE, "phone")
    _sub(AADHAAR_RE, "aadhaar")
    _sub(PAN_RE, "pan")
    _sub(CARD_RE, "card")
    return text, sorted(set(hits))
