"""Pinned official evidence. Provenance verification never approves legal applicability."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import copy
import hashlib
import json
from pathlib import Path

from tools.document_context import estimate_tokens

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "resources/regulatory/registry.json"
OFFICIAL_HOSTS = frozenset({"irdai.gov.in", "egazette.gov.in", "cioins.co.in", "sansad.in"})
MANUAL_REVIEW = "manual_verification_required"


class RegistryError(ValueError):
    pass


def validate_official_url(url: str) -> str:
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme == "https" and parsed.hostname in OFFICIAL_HOSTS and parsed.port in (None, 443) and not parsed.username and not parsed.password and not parsed.fragment
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("An allowlisted official HTTPS publisher URL is required")
    return url


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _pinned_file(root: Path, relative: str, expected_hash: str) -> bytes:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise RegistryError("Invalid registry artifact path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RegistryError("Registry artifact path escapes its root")
    try:
        if path.stat().st_size > 12_000_000:
            raise RegistryError("Registry artifact exceeds size limit")
        data = path.read_bytes()
    except OSError as exc:
        raise RegistryError("Registry artifact unavailable") from exc
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise RegistryError("Registry artifact hash integrity mismatch")
    return data


@dataclass
class SelectedEvidence:
    text: str
    metadata: dict

    def as_dict(self) -> dict:
        return copy.deepcopy(self.metadata)


class Registry:
    def __init__(self, sources: dict, clauses: list[dict], fingerprint: str):
        self.sources = sources
        self.clauses = clauses
        self.fingerprint = fingerprint

    def select(self, category: str, facts: dict, budget_units: int = 3500) -> SelectedEvidence:
        if budget_units <= 0:
            raise RegistryError("Regulatory evidence budget must be positive")
        entries, omitted, rendered = [], [], []
        used = 0
        candidates = [c for c in self.clauses if category in c["categories"] or "*" in c["categories"]]
        # Context qualifications precede substantive clauses, and ties are stable.
        candidates.sort(key=lambda c: (c.get("priority", 10), c["source_id"], c["page"], c["start"]))
        for clause in candidates:
            effective_start = _date(clause.get("effective_from"))
            effective_end = _date(clause.get("effective_to"))
            observed = _date(facts.get(clause.get("date_basis", "denial_date")))
            evidence_id = f"{clause['source_id']}:{clause['id']}"
            if observed and ((effective_start and observed < effective_start) or (effective_end and observed >= effective_end)):
                omitted.append({"evidence_id": evidence_id, "reason": "outside_effective_range"})
                continue
            if clause.get("superseded_by"):
                omitted.append({"evidence_id": evidence_id, "reason": "supersession_requires_review"})
                continue
            source = self.sources[clause["source_id"]]
            header = f"[Evidence {evidence_id}; {source['reference']}; page {clause['page']}; legal applicability requires human review]"
            labels = "; ".join("Clause " + ref for ref in clause.get("clause_references", []))
            section = header + ("\nSource clause labels: " + labels if labels else "") + "\n" + clause["text"]
            cost = estimate_tokens(section) + 2
            if used + cost > budget_units:
                omitted.append({"evidence_id": evidence_id, "reason": "context_budget"})
                continue
            used += cost
            rendered.append(section)
            entries.append({"evidence_id": evidence_id, "source_id": clause["source_id"], "clause_id": clause["id"], "page": clause["page"], "start": clause["start"], "end": clause["end"], "text": clause["text"], "source_provenance_status": "verified_source_only", "applicability_status": "requires_review", "date_basis": clause.get("date_basis"), "date_status": "known" if observed else "missing_or_ambiguous", "effective_range_known": bool(effective_start or effective_end)})
        selected_sources = list(dict.fromkeys(e["source_id"] for e in entries))
        metadata = {
            "registry_fingerprint": self.fingerprint, "requires_manual_review": True,
            "provenance_status": "pinned_official_sources", "budget_method": "utf8_byte_upper_bound",
            "budget_units": budget_units, "context_units": estimate_tokens("\n\n".join(rendered)),
            "excerpts": entries, "omitted": omitted,
            "sources": [{k: self.sources[name][k] for k in ("id", "title", "reference", "official_url", "published_date", "publisher_version", "artifact_sha256")} for name in selected_sources],
        }
        return SelectedEvidence("\n\n".join(rendered), metadata)

    def annotate(self, result: dict, evidence: SelectedEvidence) -> dict:
        result = copy.deepcopy(result)
        allowed = {entry["evidence_id"]: entry for entry in evidence.metadata["excerpts"]}
        for field in ("applicable_regulations", "potential_insurer_violations", "key_legal_points_for_appeal", "relevant_precedents"):
            for item in result.get(field, []):
                # These fields are source-owned, never inherited from model output.
                for key in ("official_source_url", "source_artifact_sha256", "source_page", "source_id", "source_reference", "source_title", "source_type", "verified", "source_case_title"):
                    item.pop(key, None)
                item["verification_status"] = MANUAL_REVIEW
                item["applicability_status"] = "requires_review"
                item["source_provenance_status"] = "unmatched"
                item["official_source_url"] = ""
                evidence_id = item.get("evidence_id")
                entry = allowed.get(evidence_id) if isinstance(evidence_id, str) else None
                quote = item.get("quoted_text")
                if not entry or not isinstance(quote, str) or quote != entry["text"]:
                    continue
                source = self.sources[entry["source_id"]]
                source_type = source.get("instrument_type", "regulatory_document")
                if field == "relevant_precedents" and source_type != "case_law":
                    continue
                if field != "relevant_precedents" and source_type == "case_law":
                    continue
                item["source_provenance_status"] = "verified_source_only"
                item["official_source_url"] = source["official_url"]
                item["source_artifact_sha256"] = source["artifact_sha256"]
                item["source_page"] = entry["page"]
                item["source_id"] = source["id"]
                item["source_reference"] = source["reference"]
                item["source_title"] = source["title"]
                item["source_type"] = source_type
                if field == "applicable_regulations":
                    item["regulation"] = source["title"]
                elif field == "potential_insurer_violations":
                    item["regulation_breached"] = source["reference"]
                elif field == "key_legal_points_for_appeal":
                    item["irdai_citation"] = source["reference"]
                else:
                    item["source_case_title"] = source["title"]
        result["citation_review_status"] = MANUAL_REVIEW
        result["regulatory_evidence"] = evidence.as_dict()
        return result


def load_registry(path: str | Path = DEFAULT_REGISTRY) -> Registry:
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
        if data.get("schema_version") != 1:
            raise RegistryError("Unsupported regulatory registry schema")
        sources = {}
        page_text = {}
        for source in data["sources"]:
            if source["id"] in sources:
                raise RegistryError("Duplicate source ID")
            validate_official_url(source["official_url"])
            for required in ("title", "reference", "publisher", "published_date", "publisher_version"):
                if not isinstance(source[required], str) or not source[required]:
                    raise RegistryError("Missing source metadata")
            if not _date(source["published_date"]):
                raise RegistryError("Invalid publication date")
            artifact = _pinned_file(path.parent, source["artifact_path"], source["artifact_sha256"])
            if not artifact.startswith(b"%PDF-"):
                raise RegistryError("Registry source has an invalid PDF signature")
            pages = json.loads(_pinned_file(path.parent, source["text_path"], source["text_sha256"]))
            by_page = {p["page"]: p["text"] for p in pages}
            if len(by_page) != len(pages) or not all(type(n) is int and n > 0 and isinstance(text, str) for n, text in by_page.items()):
                raise RegistryError("Invalid extracted source pages")
            sources[source["id"]] = source
            page_text[source["id"]] = by_page
        clauses, ids = [], set()
        for original in data["clauses"]:
            clause = dict(original)
            evidence_id = (clause["source_id"], clause["id"])
            if evidence_id in ids:
                raise RegistryError("Duplicate clause ID")
            ids.add(evidence_id)
            text = page_text[clause["source_id"]][clause["page"]]
            start, end = clause["start"], clause["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                raise RegistryError("Invalid clause offset range")
            if not isinstance(clause["categories"], list) or not clause["categories"] or not all(isinstance(c, str) for c in clause["categories"]):
                raise RegistryError("Invalid clause categories")
            for field in ("effective_from", "effective_to"):
                if clause.get(field) is not None and not _date(clause[field]):
                    raise RegistryError("Invalid effective date")
            if clause.get("date_basis") not in ("policy_start_date", "denial_date"):
                raise RegistryError("Invalid applicability date basis")
            clause["text"] = text[start:end]
            if original.get("quoted_text") is not None and original["quoted_text"] != clause["text"]:
                raise RegistryError("Clause quotation integrity mismatch")
            references = clause.get("clause_references", [])
            import re
            if not isinstance(references, list) or any(not isinstance(ref, str) or not re.fullmatch(r"\d+(?:\.\d+)*(?:\([a-z0-9]+\))?", ref) for ref in references):
                raise RegistryError("Invalid curated clause reference")
            clauses.append(clause)
        return Registry(sources, clauses, hashlib.sha256(raw).hexdigest())
    except RegistryError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RegistryError(f"Invalid or unavailable regulatory registry: {type(exc).__name__}") from exc
