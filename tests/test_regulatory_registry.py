import hashlib
import json
from pathlib import Path

import pytest

from tools.regulatory_registry import RegistryError, load_registry
from tools.import_regulatory_source import validate_official_url, download_official_pdf


def make_registry(tmp_path, **clause_fields):
    artifact = tmp_path / "rule.pdf"
    artifact.write_bytes(b"%PDF-1.4\nPinned official test artifact\n")
    text = "Before. Clause 13: Claims require careful review. After."
    pages = tmp_path / "rule.pages.json"
    pages.write_text(json.dumps([{"page": 1, "text": text}]), encoding="utf-8")
    clause = {"id": "review", "source_id": "official-rule", "page": 1, "start": 8, "end": 49, "categories": ["other"], "effective_from": None, "effective_to": None, "date_basis": "denial_date", **clause_fields}
    data = {"schema_version": 1, "sources": [{"id": "official-rule", "title": "Official rule", "reference": "CIR/2024/1", "official_url": "https://irdai.gov.in/documents/rule.pdf", "publisher": "IRDAI", "published_date": "2024-05-29", "publisher_version": "1", "artifact_path": "rule.pdf", "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "text_path": "rule.pages.json", "text_sha256": hashlib.sha256(pages.read_bytes()).hexdigest()}], "clauses": [clause]}
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_pinned_evidence_has_provenance_but_requires_case_review(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {}, 2000)
    assert "Clause 13: Claims require careful review." in selected.text
    assert selected.as_dict()["requires_manual_review"]
    assert selected.as_dict()["sources"][0]["official_url"] == "https://irdai.gov.in/documents/rule.pdf"
    assert registry.fingerprint


@pytest.mark.parametrize("filename", ["rule.pdf", "rule.pages.json"])
def test_altered_source_bytes_cannot_be_used(tmp_path, filename):
    path = make_registry(tmp_path)
    with (tmp_path / filename).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(RegistryError, match="hash|integrity"):
        load_registry(path)


def test_registry_artifact_paths_cannot_escape_registry_root(tmp_path):
    path = make_registry(tmp_path)
    data = json.loads(path.read_text())
    data["sources"][0]["artifact_path"] = "../outside.pdf"
    path.write_text(json.dumps(data))
    with pytest.raises(RegistryError, match="path"):
        load_registry(path)


def test_unknown_or_forged_citation_cannot_be_promoted(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {}, 2000)
    result = registry.annotate({"applicable_regulations": [{"evidence_id": "invented", "verification_status": "verified", "source_provenance_status": "verified", "official_source_url": "https://irdai.gov.in/"}]}, selected)
    citation = result["applicable_regulations"][0]
    assert citation["verification_status"] == "manual_verification_required"
    assert citation["source_provenance_status"] == "unmatched"
    assert citation["official_source_url"] == ""


def test_real_evidence_id_still_requires_exact_quote_and_human_review(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {"denial_date": "2025-01-01"}, 2000)
    evidence = selected.as_dict()["excerpts"][0]
    result = registry.annotate({"applicable_regulations": [{"evidence_id": evidence["evidence_id"], "quoted_text": evidence["text"]}]}, selected)
    citation = result["applicable_regulations"][0]
    assert citation["source_provenance_status"] == "verified_source_only"
    assert citation["verification_status"] == "manual_verification_required"
    assert citation["applicability_status"] == "requires_review"


def test_effective_range_excludes_outside_dates_and_marks_missing_dates(tmp_path):
    registry = load_registry(make_registry(tmp_path, effective_from="2024-06-01", effective_to="2025-01-01"))
    assert registry.select("other", {"denial_date": "2024-05-31"}, 2000).as_dict()["excerpts"] == []
    assert registry.select("other", {"denial_date": "2024-06-01"}, 2000).as_dict()["excerpts"]
    assert registry.select("other", {"denial_date": "2025-01-01"}, 2000).as_dict()["excerpts"] == []
    assert registry.select("other", {}, 2000).as_dict()["requires_manual_review"]


@pytest.mark.parametrize("url", ["http://irdai.gov.in/rule.pdf", "https://irdai.gov.in.evil.test/rule.pdf", "https://user@irdai.gov.in/rule.pdf", "https://127.0.0.1/rule.pdf", "https://irdai.gov.in:1234/rule.pdf"])
def test_official_import_rejects_untrusted_urls(url):
    with pytest.raises(ValueError, match="official|HTTPS"):
        validate_official_url(url)


def test_import_rejects_redirect_before_contacting_untrusted_host():
    from tools.import_regulatory_source import OfficialRedirectHandler
    handler = OfficialRedirectHandler()
    with pytest.raises(ValueError):
        handler.redirect_request(None, None, 302, "Found", {}, "https://evil.test/rule.pdf")


def test_bad_quote_offsets_are_rejected(tmp_path):
    with pytest.raises(RegistryError, match="offset|range"):
        load_registry(make_registry(tmp_path, end=9999))


def test_circular_id_cannot_verify_an_invented_precedent(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {}, 2000)
    entry = selected.metadata["excerpts"][0]
    result = registry.annotate({"relevant_precedents": [{"case_summary": "Invented Supreme Court award", "evidence_id": entry["evidence_id"], "quoted_text": entry["text"]}]}, selected)
    assert result["relevant_precedents"][0]["source_provenance_status"] == "unmatched"


def test_citation_identity_and_stale_source_fields_cannot_be_supplied_by_model(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {}, 2000)
    entry = selected.metadata["excerpts"][0]
    result = registry.annotate({"applicable_regulations": [{"regulation": "Invented regulation", "evidence_id": entry["evidence_id"], "quoted_text": entry["text"], "source_page": 999, "source_artifact_sha256": "fake"}]}, selected)
    citation = result["applicable_regulations"][0]
    assert citation["regulation"] == "Official rule"
    assert citation["source_page"] == 1
    bad = registry.annotate({"applicable_regulations": [{"evidence_id": "unknown", "source_page": 999, "source_artifact_sha256": "fake"}]}, selected)["applicable_regulations"][0]
    assert "source_page" not in bad and "source_artifact_sha256" not in bad


def test_non_string_evidence_ids_are_unmatched_instead_of_crashing(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {}, 2000)
    result = registry.annotate({"applicable_regulations": [{"evidence_id": {"bad": "id"}, "quoted_text": "the"}]}, selected)
    assert result["applicable_regulations"][0]["source_provenance_status"] == "unmatched"


def test_short_incidental_quote_cannot_verify_a_generated_citation(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    selected = registry.select("other", {}, 2000)
    entry = selected.metadata["excerpts"][0]
    result = registry.annotate({"applicable_regulations": [{"evidence_id": entry["evidence_id"], "quoted_text": "Claims"}]}, selected)
    assert result["applicable_regulations"][0]["source_provenance_status"] == "unmatched"
