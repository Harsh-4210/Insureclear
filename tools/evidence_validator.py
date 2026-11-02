"""Evidence checks for generated appeal letters.

The validator is deliberately conservative: it reports concrete, extractable
claims that cannot be found in the supplied source material and does not try to
judge whether an argument is legally correct.
"""

from dataclasses import dataclass, field
import re
from typing import Mapping


@dataclass(frozen=True)
class EvidenceIssue:
    category: str
    value: str
    message: str


@dataclass
class EvidenceValidation:
    """Result returned by :func:`validate_appeal_letter`."""

    valid: bool
    issues: list[EvidenceIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[EvidenceIssue]:
        return self.issues

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [
                {"category": i.category, "value": i.value, "message": i.message}
                for i in self.issues
            ],
        }


_DATE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}|"
    r"[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b",
    re.I,
)
_AMOUNT = re.compile(
    r"(?:(?:₹|INR|Rs\.?)\s*[\d,]+(?:\.\d+)?|"
    r"[\d,]+(?:\.\d+)?\s*(?:rupees|INR|lakhs?|crores?))",
    re.I,
)
_CLAUSE = re.compile(
    r"\b(?:clause|section|regulation|rule|article|paragraph|para|exclusion)"
    r"\s*(?:no\.?|number)?\s*[A-Za-z]?(?:\d+(?:\.\d+)*(?:\([a-z0-9]+\))?)",
    re.I,
)
_ID = re.compile(
    r"\b(?:policy|claim|case|member|certificate|customer|UHID|"
    r"reference|ref(?:erence)?)\s*(?:number|no\.?|#|id)?\s*[:\-]?\s*"
    r"(?=[A-Z0-9/_-]*\d)[A-Z0-9][A-Z0-9/_-]{3,}\b",
    re.I,
)
_BARE_ID = re.compile(
    r"\b[A-Z]{2,}(?:/[A-Z0-9]+|-[A-Z0-9]+){1,}(?:/\d{2,})?/?(?![A-Za-z0-9])"
)
_CASE_LAW = re.compile(
    r"\b[A-Z][A-Za-z.&' -]{2,}\s+v(?:s?\.?|ersus)\s+[A-Z][A-Za-z.&' -]{2,}"
    r"|(?:AIR\s+\d{4}|SCC\s+\d{4}|\(\d{4}\))",
    re.I,
)
_MEDICAL = re.compile(
    r"\b(?:medically\s+necessary|clinically\s+(?:indicated|proven)|"
    r"standard\s+of\s+care|doctor\s+(?:confirmed|certified)|"
    r"diagnosed\s+with|requires?\s+(?:surgery|treatment|hospitalisation)|"
    r"life[- ]threatening|pre[- ]existing\s+(?:disease|condition))\b",
    re.I,
)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.replace("\u00a0", " ").replace("\u202f", " ").lower())


def _present(value: str, source: str) -> bool:
    if _normalise(value) in _normalise(source):
        return True
    clause_number = re.fullmatch(
        r"(?:clause|section|regulation|rule|article|paragraph|para|exclusion)"
        r"\s*(?:no\.?|number)?\s*([a-z]?\d+(?:\.\d+)*(?:\([a-z0-9]+\))?)",
        value.strip(),
        re.I,
    )
    if clause_number and re.search(
        rf"(?<![\d.]){re.escape(clause_number.group(1))}(?![\d.])",
        source,
        re.I,
    ):
        return True
    amount = re.search(r"(?:₹|INR|Rs\.?)\s*([\d,]+(?:\.\d+)?)", value, re.I)
    if amount and re.search(r"\d[\d,]*(?:\.\d+)?", source):
        value_digits = re.sub(r"\D", "", amount.group())
        source_digits = {re.sub(r"\D", "", match) for match in re.findall(r"\d[\d,]*(?:\.\d+)?", source)}
        return value_digits in source_digits
    return False


def _add_missing(issues: list[EvidenceIssue], category: str, values, source: str):
    seen: set[str] = set()
    for value in values:
        key = _normalise(value)
        if not key or key in seen or _present(value, source):
            continue
        seen.add(key)
        issues.append(EvidenceIssue(
            category, value, f"{category.replace('_', ' ').capitalize()} is not present in supplied sources"
        ))


def validate_appeal_letter(
    letter: str,
    sources: Mapping[str, str] | None = None,
) -> EvidenceValidation:
    """Check concrete claims in ``letter`` against denial/policy/regulatory text.

    ``sources`` may contain ``denial``, ``policy``, and ``regulatory`` keys.
    Missing/empty sources are ignored, allowing callers to validate only the
    documents they actually supplied.
    """
    if not isinstance(letter, str) or not letter.strip():
        return EvidenceValidation(False, [
            EvidenceIssue("empty_letter", "", "Appeal letter is empty")
        ])
    source_text = "\n".join(str(v) for v in (sources or {}).values() if v)
    if not source_text.strip():
        return EvidenceValidation(False, [
            EvidenceIssue("missing_sources", "", "No denial, policy, or regulatory source text supplied")
        ])

    issues: list[EvidenceIssue] = []
    _add_missing(issues, "unsupported_id", _ID.findall(letter), source_text)
    _add_missing(issues, "unsupported_id", _BARE_ID.findall(letter), source_text)
    _add_missing(issues, "unsupported_date", _DATE.findall(letter), source_text)
    _add_missing(issues, "unsupported_amount", _AMOUNT.findall(letter), source_text)
    _add_missing(issues, "unsupported_clause", _CLAUSE.findall(letter), source_text)

    for value in _CASE_LAW.findall(letter):
        value = value.strip()
        if value and not _present(value, source_text):
            issues.append(EvidenceIssue(
                "invented_case_law", value,
                "Case-law citation is not present in supplied sources",
            ))

    for sentence in re.split(r"(?<=[.!?])\s+", letter):
        medical_terms = _MEDICAL.findall(sentence)
        if medical_terms and not any(_present(term, source_text) for term in medical_terms):
            issues.append(EvidenceIssue(
                "unsupported_medical_claim", sentence.strip(),
                "Medical claim is not supported by supplied sources",
            ))

    return EvidenceValidation(not issues, issues)
