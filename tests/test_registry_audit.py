"""Metadata audit regressions; all changed artifacts live in pytest temporary roots."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.regulatory_registry import load_registry
from tools.audit_regulatory_registry import audit_registry as audit
from test_regulatory_registry import make_registry


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/audit_regulatory_registry.py"


def run_audit(*args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def test_default_cli_audits_real_pinned_corpus_without_legal_acceptance():
    result = run_audit()
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["source_count"] == 3
    assert report["excerpt_count"] == 9
    assert report["integrity_status"] == "verified_at_load"
    assert report["requires_manual_review"] is True
    assert report["applicability_status"] == "requires_review"
    assert "human_applicability_review_required" in report["review_reasons"]
    counts = {source["id"]: source["excerpt_count"] for source in report["sources"]}
    assert counts == {
        "health-master-2024": 9,
        "policyholder-interests-master-2024": 0,
        "insurance-products-regulations-2024": 0,
    }
    assert set(report["coverage"]["sources_without_excerpts"]) == {
        "policyholder-interests-master-2024", "insurance-products-regulations-2024",
    }
    assert len(report["gaps"]["missing_effective_ranges"]) == 9
    assert len(report["gaps"]["unknown_supersession"]) == 9
    assert report["coverage"]["category_excerpt_counts"]["*"] == 4
    assert all("text" not in entry and "quoted_text" not in entry for entry in report["excerpts"])
    assert "This Master circular shall" not in result.stdout


def test_unknown_dates_are_preserved_without_publication_date_fallback(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    before = copy.deepcopy(registry.clauses)
    report = audit(registry)
    entry = report["excerpts"][0]
    assert entry["effective_from"] is None
    assert entry["effective_to"] is None
    assert entry["date_basis"] == "denial_date"
    assert entry["superseded_by"] is None
    assert entry["supersession_status"] == "unknown"
    assert "effective_from_unknown" in entry["review_reasons"]
    assert "effective_to_unknown" in entry["review_reasons"]
    assert registry.clauses == before
    assert report["sources"][0]["published_date"] == "2024-05-29"


def test_missing_date_basis_is_a_review_gap_in_a_registry_snapshot(tmp_path):
    registry = load_registry(make_registry(tmp_path))
    del registry.clauses[0]["date_basis"]
    report = audit(registry)
    assert report["excerpts"][0]["date_basis"] is None
    assert report["gaps"]["missing_date_basis"] == ["official-rule:review"]
    assert "date_basis_missing_or_invalid" in report["excerpts"][0]["review_reasons"]


def test_recorded_supersession_and_known_dates_still_need_human_review(tmp_path):
    registry = load_registry(make_registry(
        tmp_path, effective_from="2024-06-01", effective_to="2025-01-01",
        superseded_by="replacement:clause",
    ))
    report = audit(registry)
    entry = report["excerpts"][0]
    assert entry["effective_from"] == "2024-06-01"
    assert entry["effective_to"] == "2025-01-01"
    assert entry["superseded_by"] == "replacement:clause"
    assert entry["supersession_status"] == "recorded_requires_review"
    assert "supersession_requires_review" in entry["review_reasons"]
    assert entry["applicability_status"] == "requires_review"
    assert report["gaps"]["missing_effective_ranges"] == []
    assert report["requires_manual_review"] is True


@pytest.mark.parametrize("filename", ["rule.pdf", "rule.pages.json"])
def test_cli_rejects_tampered_pinned_bytes(tmp_path, filename):
    path = make_registry(tmp_path)
    with (tmp_path / filename).open("ab") as stream:
        stream.write(b"tampered synthetic bytes")
    result = run_audit("--registry", path)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["integrity_status"] == "failed"
    assert report["requires_manual_review"] is True
    assert "excerpts" not in report
    assert "tampered synthetic bytes" not in result.stdout


def test_cli_rejects_missing_corpus(tmp_path):
    result = run_audit("--registry", tmp_path / "absent.json")
    assert result.returncode != 0
    assert json.loads(result.stdout)["integrity_status"] == "failed"


@pytest.mark.parametrize("section", ["sources", "clauses"])
def test_cli_rejects_empty_corpus(tmp_path, section):
    path = make_registry(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data[section] = []
    if section == "sources":
        data["clauses"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_audit("--registry", path)
    assert result.returncode != 0
    assert json.loads(result.stdout)["integrity_status"] == "failed"


def test_valid_cli_is_metadata_only_and_does_not_write_corpus(tmp_path):
    path = make_registry(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = run_audit("--registry", path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["source_count"] == 1
    assert report["excerpt_count"] == 1
    assert report["sources"][0]["artifact_sha256"]
    assert "Claims require careful review" not in result.stdout
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
