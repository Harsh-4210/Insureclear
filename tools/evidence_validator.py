"""Evidence checks for generated appeal letters.

The validator is deliberately conservative: it reports concrete, extractable
claims that cannot be found in the supplied source material and does not try to
judge whether an argument is legally correct.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import date
import calendar
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
    r"(?<![A-Za-z0-9/_-])(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}|"
    r"[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b(?![A-Za-z0-9/_-])",
    re.I,
)
_NUMBER = r"(?:\d{1,3}(?:,\s*\d{2,3})+|\d+)(?:\.\d+)?"
_AMOUNT = re.compile(
    rf"(?:(?:₹|INR|Rs\.?)\s*{_NUMBER}(?:\s*(?:lakhs?|crores?))?|"
    rf"{_NUMBER}\s*(?:rupees|INR|lakhs?|crores?))",
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
    r"\b(?=[A-Z0-9/-]*\d)[A-Z]{2,}(?:/[A-Z0-9]+|-[A-Z0-9]+){1,}(?:/\d{2,})?/?(?![A-Za-z0-9])"
)
_CASE_LAW = re.compile(
    r"(?<!/)\b[A-Z][A-Za-z&' -]{2,}\.?\s+v(?:s?\.?|ersus)\s+[A-Z][A-Za-z&' -]{2,}"
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


def _contains_reference(value: str, source: str) -> bool:
    # Permit formatting differences, but never prefixes of longer identifiers,
    # numbers or clause references (e.g. POL-123 versus POL-1234).
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9/_-])" + r"[^a-z0-9]*".join(map(re.escape, tokens)) + r"(?![a-z0-9]|[./_-][a-z0-9])"
    return re.search(pattern, source, re.I) is not None


def _amount_value(value: str):
    compact = re.sub(r"(?<=,)\s+(?=\d)", "", value)
    match = re.search(r"[\d,]+(?:\.\d+)?", compact)
    if not match:
        return None
    try:
        number = Decimal(match.group().replace(",", ""))
    except InvalidOperation:
        return None
    lower = value.lower()
    if "lakh" in lower:
        number *= 100000
    elif "crore" in lower:
        number *= 10000000
    return number


def _date_value(value: str):
    value = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", value.lower())
    numeric = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value.strip())
    try:
        if numeric:
            day, month, year = map(int, numeric.groups())
            return date(year, month, day)
        parts = re.sub(r",", " ", value).split()
        months = {name.lower(): number for number in range(1, 13) for name in (calendar.month_name[number], calendar.month_abbr[number])}
        months["sept"] = 9
        if len(parts) == 3 and len(parts[2]) == 4:
            if parts[0].isdigit() and parts[1] in months:
                return date(int(parts[2]), months[parts[1]], int(parts[0]))
            if parts[0] in months and parts[1].isdigit():
                return date(int(parts[2]), months[parts[0]], int(parts[1]))
    except ValueError:
        pass
    return None


def _present(value: str, source: str) -> bool:
    if _DATE.fullmatch(value.strip()):
        normalized = _date_value(value)
        if normalized is not None:
            return any(_date_value(candidate) == normalized for candidate in _DATE.findall(source))
    if _AMOUNT.fullmatch(value.strip()):
        amount = _amount_value(value)
        return amount is not None and any(_amount_value(candidate) == amount for candidate in _AMOUNT.findall(source))
    if _contains_reference(value, source):
        return True
    identifier = re.search(
        r"(?:(?:policy|claim|case|member|certificate|customer|UHID|reference|ref(?:erence)?)"
        r"\s*(?:number|no\.?|#|id)?\s*[:\-]?\s*)"
        r"([A-Z0-9][A-Z0-9/_-]{3,})",
        value,
        re.I,
    )
    if identifier and _contains_reference(identifier.group(1), source):
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
    return False


_DEADLINE_CONTEXT = re.compile(r"\b(?:respond|response|reply|settle|settlement|payment|pay|resolve|resolution|escalat\w*|confirmation)\b", re.I)
_DEADLINE_COUNT = re.compile(r"\b(\d+|one|two|three|five|seven|ten|fifteen|thirty|sixty|ninety)[\s\-\u2010-\u2015]*(?:(working|business|calendar)\s+)?(days?|weeks?|hours?)\b", re.I)
_COUNT_WORDS = dict(one=1, two=2, three=3, five=5, seven=7, ten=10, fifteen=15, thirty=30, sixty=60, ninety=90)


def _deadline_spans(text):
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if not _DEADLINE_CONTEXT.search(sentence):
            continue
        for match in _DEADLINE_COUNT.finditer(sentence):
            count, kind, unit = match.groups()
            number = int(count) if count.isdecimal() else _COUNT_WORDS[count.lower()]
            yield match.group(), (number, "working" if (kind or "").lower() in {"business", "working"} else (kind or "").lower(), unit.lower().rstrip("s"))


def sanitize_unsupported_references(
    letter: str, validation: EvidenceValidation
) -> str:
    """Remove unsupported concrete references before a letter can be emitted."""
    sanitized = letter
    replacements = {
        "unsupported_id": "the cited reference",
        "unsupported_medical_claim": (
            "The supplied documents do not establish this medical assertion"
        ),
        "invented_case_law": "the cited legal authority",
    }
    for issue in validation.issues:
        if issue.category in {"unsupported_clause", "unsupported_deadline", "invented_case_law"} and issue.value:
            # Preserve the matched span across sentence and line boundaries.
            terminal = issue.value[-1] if issue.value[-1] in ".!?" else ""
            marked = sanitized.replace(issue.value, "\0" + terminal)
            parts = re.split(r"(?<=[.!?])\s+|\n+", marked)
            sanitized = "\n".join("[Unsupported statement removed; review the source wording.]" if "\0" in part else part for part in parts)
            continue
        replacement = replacements.get(issue.category)
        if replacement and issue.value:
            sanitized = sanitized.replace(issue.value, replacement)
    return sanitized


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

    supported_deadlines = {key for _, key in _deadline_spans(source_text)}
    deadline_issues = [EvidenceIssue("unsupported_deadline", value, "Numeric response or escalation deadline lacks matching source context") for value, key in _deadline_spans(letter) if key not in supported_deadlines]
    case_text = "\n".join(str((sources or {}).get(key) or "") for key in ("denial", "policy"))
    issues: list[EvidenceIssue] = deadline_issues
    for value in _ID.findall(letter):
        patient_id = bool(re.match(r"(?:policy|claim|case|member|certificate|customer|UHID)\b", value, re.I))
        _add_missing(issues, "unsupported_id", [value], case_text if patient_id else source_text)
    _add_missing(issues, "unsupported_id", _BARE_ID.findall(letter), source_text)
    _add_missing(issues, "unsupported_date", _DATE.findall(letter), source_text)
    _add_missing(issues, "unsupported_amount", _AMOUNT.findall(letter), case_text)
    clause_matches = list(_CLAUSE.finditer(letter))
    regulatory_text = str((sources or {}).get("regulatory") or "")
    regulatory_bindings = set()

    def clause_key(value):
        return re.sub(r"^\D+", "", value.lower()).replace(" ", "")

    def has_regulatory_context(match):
        before = letter[max(0, match.start() - 160):match.start()].lower()
        after = letter[match.end():match.end() + 100].lower()
        return (
            match.group().lower().startswith(("regulation", "rule", "article", "paragraph", "para"))
            or bool(re.search(r"(?:irdai|master\s+circular|regulatory|gazette|same\s+circular)[^.!?\n]{0,120}$", before))
            or bool(re.search(r"^[^.!?\n]{0,80}(?:circular|irdai|gazette)", after))
        )

    for match in clause_matches:
        if has_regulatory_context(match) and _present(match.group(), regulatory_text):
            regulatory_bindings.add(clause_key(match.group()))
            regulatory_bindings.add(re.sub(r"\([a-z0-9]+\)$", "", clause_key(match.group())))
    for match in clause_matches:
        value = match.group()
        before = letter[max(0, match.start() - 30):match.start()].lower()
        explicitly_policy = bool(re.search(r"policy(?:'s)?\s*$", before)) or value.lower().startswith("exclusion")
        use_regulatory = not explicitly_policy and (has_regulatory_context(match) or clause_key(value) in regulatory_bindings)
        _add_missing(issues, "unsupported_clause", [value], source_text if use_regulatory else case_text)

    for value in _CASE_LAW.findall(letter):
        value = value.strip()
        if value and not _present(value, source_text):
            issues.append(EvidenceIssue(
                "invented_case_law", value,
                "Case-law citation is not present in supplied sources",
            ))

    for sentence in re.split(r"(?<=[.!?])\s+", letter):
        medical_terms = _MEDICAL.findall(sentence)
        if medical_terms and not any(_present(term, case_text) for term in medical_terms):
            issues.append(EvidenceIssue(
                "unsupported_medical_claim", sentence.strip(),
                "Medical claim is not supported by supplied sources",
            ))

    return EvidenceValidation(not issues, issues)
