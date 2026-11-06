"""
Orchestrator — Main Pipeline
Runs all 5 agents in sequence with revision loop.
Handles checkpointing (resume from last successful stage),
timing, validation, and assembles the final output package.
"""

import sys
import time
import json
from typing import Callable, Any
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.policy_evidence import annotate_policy_evidence
from tools.regulatory_registry import load_registry
from tools.document_context import retrieval_fingerprint
from tools.pdf_reader import extract_text_from_pdf
from tools.io_utils import prepare_session, save_final_output
from tools.llm_client import get_stats
from tools.agent_validation import validate_agent_output
from tools.evidence_validator import sanitize_unsupported_references, validate_appeal_letter
from agents import auditor, policy_analyst, irdai_checker, appeal_writer, judge


MAX_REVISIONS = 2
MIN_APPROVE_SCORE = 0.75


ProgressCallback = Callable[[dict[str, Any]], None]


def _validate_text(text: str, source: str, min_words: int = 10) -> None:
    """Validate extracted text has enough content to work with."""
    if not text or not text.strip():
        raise ValueError(f"No text extracted from {source}. Is the file empty or corrupted?")
    word_count = len(text.split())
    if word_count < min_words:
        raise ValueError(
            f"Only {word_count} words extracted from {source}. "
            f"Expected at least {min_words}. The file may be scanned — ensure Tesseract OCR is installed."
        )


def _timed(label: str):
    """Context manager that prints how long a step took."""
    class Timer:
        def __init__(self):
            self.elapsed = 0
        def __enter__(self):
            self._start = time.time()
            return self
        def __exit__(self, *args):
            self.elapsed = time.time() - self._start
            print(f"  ⏱  {label}: {self.elapsed:.1f}s")
    return Timer()


def run_pipeline(
    denial_pdf: str,
    policy_pdf: str,
    case_id: str,
    denial_text: str = None,
    policy_text: str = None,
    progress_callback: ProgressCallback | None = None,
    regulatory_text: str = None,
) -> dict:
    """
    Full pipeline: PDF inputs → appeal letter + scorecard.

    Args:
        denial_pdf: Path to the rejection letter PDF
        policy_pdf: Path to the insurance policy PDF
        case_id: Unique ID for this case (used for checkpointing)
        denial_text: Pre-extracted denial text (skips PDF reading if provided)
        policy_text: Pre-extracted policy text (skips PDF reading if provided)
        regulatory_text: Optional unverified research lead; never authoritative evidence

    Returns:
        Dict with all outputs and the final appeal letter path
    """
    pipeline_start = time.time()

    def emit(stage: str, message: str, percent: int | None = None, state: str | None = None) -> None:
        if progress_callback:
            progress_callback({
                "stage": stage,
                "message": message,
                "percent": percent,
                "state": state,
                "case_id": case_id,
            })

    print(f"\n{'='*60}")
    print(f"  InsureClear — Appeal Pipeline")
    print(f"  Case ID: {case_id}")
    print(f"{'='*60}")
    emit("starting", "Preparing pipeline", 0, "running")

    # ── Step 0: Extract text from PDFs ───────────────────────────
    if not denial_text or not policy_text:
        print("\n[Step 0] Reading PDF documents...")
        emit("extracting", "Extracting text from uploaded documents", 5, "running")
        with _timed("PDF extraction"):
            if not denial_text:
                denial_text = extract_text_from_pdf(denial_pdf)
            if not policy_text:
                policy_text = extract_text_from_pdf(policy_pdf)

    print(f"  Denial letter: {len(denial_text.split())} words")
    print(f"  Policy document: {len(policy_text.split())} words")

    # Validate extracted text
    _validate_text(denial_text, "denial letter")
    _validate_text(policy_text, "policy document")
    registry = load_registry()
    prepare_session(case_id, denial_text, policy_text, regulatory_text, retrieval_fingerprint() + registry.fingerprint + ":policy-evidence-1:quality-2")

    # ── Agent 1: Auditor ──────────────────────────────────────────
    print("\n[Step 1/5] Auditor — Parsing documents...")
    emit("auditor", "Auditor is parsing denial and policy documents", 15, "running")
    with _timed("Auditor") as t1:
        auditor_result = auditor.run(denial_text, policy_text, case_id)
        auditor_result = validate_agent_output("Auditor", auditor_result)

    print(f"\n  Extracted:")
    print(f"  • Insurer     : {auditor_result.get('insurer_name')}")
    print(f"  • Treatment   : {auditor_result.get('treatment_or_procedure')}")
    print(f"  • Denial type : {auditor_result.get('denial_reason_category')}")
    print(f"  • Claim amount: {auditor_result.get('claim_amount')}")

    # ── Agent 2: Policy Analyst ───────────────────────────────────
    print("\n[Step 2/5] Policy Analyst — Examining policy terms...")
    emit("policy_analyst", "Policy Analyst is checking clauses and exclusions", 30, "running")
    with _timed("Policy Analyst") as t2:
        policy_result = policy_analyst.run(policy_text, auditor_result, case_id)
        policy_result = validate_agent_output("Policy Analyst", policy_result)
        policy_result = annotate_policy_evidence(policy_result, policy_text)

    valid = policy_result.get("rejection_appears_valid")
    print(f"\n  Rejection legitimacy: {'⚠️  Appears valid' if valid else '✓ Challengeable'}")

    # ── Agent 3: IRDAI Checker ────────────────────────────────────
    print("\n[Step 3/5] IRDAI Checker — Checking against regulations...")
    emit("irdai_checker", "IRDAI Checker is matching the case against regulations", 50, "running")
    with _timed("IRDAI Checker") as t3:
        irdai_result = irdai_checker.run(auditor_result, policy_result, case_id)
        irdai_result = validate_agent_output("IRDAI Checker", irdai_result)
        irdai_result["verified_policy_context"] = policy_result.get("verified_policy_context", "")

    pathway = irdai_result.get("appeal_pathway", {})
    print(f"\n  Recommended appeal: {pathway.get('recommended_first_step')}")
    print(f"  Success estimate  : {pathway.get('estimated_success_probability')}")

    violations = irdai_result.get("potential_insurer_violations", [])
    if violations:
        print(f"  Violations found  : {len(violations)}")

    # ── Agent 4: Appeal Writer ────────────────────────────────────
    print("\n[Step 4/5] Appeal Writer — Drafting letter...")
    emit("appeal_writer", "Appeal Writer is drafting the appeal letter", 70, "running")
    with _timed("Appeal Writer") as t4:
        letter = appeal_writer.run(auditor_result, policy_result, irdai_result, case_id)
        letter = validate_agent_output("Appeal Writer", letter)
    print(f"  Letter length: {len(letter.split())} words")

    # ── Agent 5: Judge ────────────────────────────────────────────
    print("\n[Step 5/5] Judge — Reviewing quality...")
    emit("judge", "Judge is reviewing the draft for quality and hallucinations", 85, "running")
    with _timed("Judge") as t5:
        judge_result = judge.run(letter, auditor_result, irdai_result, case_id)
        judge_result = validate_agent_output("Judge", judge_result)

    score = judge_result.get("overall_score", 0)
    recommendation = judge_result.get("recommendation", "APPROVE")
    print(f"\n  Overall score : {score:.2f}/1.00")
    print(f"  Recommendation: {recommendation}")

    if score < MIN_APPROVE_SCORE and recommendation == "APPROVE":
        recommendation = "REVISE"
        print(f"  Threshold    : score below {MIN_APPROVE_SCORE:.2f}, forcing revision")

    emit("review", f"Initial review finished with score {score:.2f}", 90, "running")

    # ── Revision Loop ─────────────────────────────────────────────
    revision_count = 0
    while recommendation == "REVISE" and revision_count < MAX_REVISIONS:
        revision_count += 1
        print(f"\n{'─'*60}")
        print(f"  📝 Revision #{revision_count} — Judge requested improvements")
        print(f"{'─'*60}")
        emit("revision", f"Applying revision #{revision_count}", 90, "running")

        for change in judge_result.get("if_revise_top_changes", [])[:3]:
            print(f"  → {change}")

        # Revise the letter
        with _timed(f"Revision #{revision_count}"):
            letter = appeal_writer.revise(
                original_letter=letter,
                judge_feedback=judge_result,
                auditor_output=auditor_result,
                irdai_output=irdai_result,
                case_id=case_id,
                revision_number=revision_count,
            )
            letter = validate_agent_output("Appeal Writer revision", letter)

        # Clear judge checkpoint so it re-evaluates the revised letter
        from tools.io_utils import get_checkpoint_path
        judge_cp = get_checkpoint_path(case_id, "judge")
        if judge_cp.exists():
            judge_cp.unlink()

        # Re-judge the revised letter
        print(f"\n  [Judge] Re-evaluating revision #{revision_count}...")
        with _timed(f"Judge re-evaluation #{revision_count}"):
            judge_result = judge.run(letter, auditor_result, irdai_result, case_id)
            judge_result = validate_agent_output("Judge", judge_result)

        score = judge_result.get("overall_score", 0)
        recommendation = judge_result.get("recommendation", "APPROVE")

        if score < MIN_APPROVE_SCORE and recommendation == "APPROVE":
            recommendation = "REVISE"

        print(f"\n  Revised score : {score:.2f}/1.00")
        print(f"  Recommendation: {recommendation}")
        emit("revision_review", f"Revision #{revision_count} scored {score:.2f}", 95, "running")

    if revision_count > 0:
        print(f"\n  Total revisions: {revision_count}")

    reviewed_letter = letter

    # Ground the final draft in the documents before it is written to disk.
    evidence_validation = validate_appeal_letter(
        letter,
        {
            "denial": denial_text,
            "policy": policy_text,
            "regulatory": irdai_result.get("verified_source_context", ""),
        },
    )
    for evidence_attempt in range(2):
        if evidence_validation.valid:
            break
        evidence_feedback = {
            "hallucination_flags": [
                f"{issue.category}: {issue.value}" for issue in evidence_validation.issues
            ],
            "missing_elements": [],
            "weak_arguments": [],
            "if_revise_top_changes": [
                "Remove or rewrite every claim listed as unsupported. Use only facts present in the supplied documents or ask for clarification."
            ],
        }
        with _timed("Evidence correction"):
            corrected_letter = appeal_writer.revise(
                original_letter=letter,
                judge_feedback=evidence_feedback,
                auditor_output=auditor_result,
                irdai_output=irdai_result,
                case_id=case_id,
                revision_number=revision_count + evidence_attempt + 1,
            )
        corrected_letter = validate_agent_output("Appeal Writer evidence correction", corrected_letter)
        corrected_validation = validate_appeal_letter(
            corrected_letter,
            {
                "denial": denial_text,
                "policy": policy_text,
                "regulatory": irdai_result.get("verified_source_context", ""),
            },
        )
        if corrected_validation.valid:
            letter = corrected_letter
            evidence_validation = corrected_validation
            print("\n  Evidence correction: passed")
        letter = corrected_letter
        evidence_validation = corrected_validation
    if not evidence_validation.valid:
        sanitized_letter = sanitize_unsupported_references(letter, evidence_validation)
        sanitized_validation = validate_appeal_letter(
            sanitized_letter,
            {
                "denial": denial_text,
                "policy": policy_text,
                "regulatory": irdai_result.get("verified_source_context", ""),
            },
        )
        if sanitized_validation.valid:
            letter = sanitized_letter
            evidence_validation = sanitized_validation
            print("\n  Evidence sanitization: passed")
    if letter != reviewed_letter:
        # Evidence rewriting changes the draft after the quality revision loop.
        # The final scorecard must assess the exact letter that will be saved.
        from tools.io_utils import get_checkpoint_path, save_checkpoint, load_checkpoint
        get_checkpoint_path(case_id, "judge").unlink(missing_ok=True)
        writer_state = load_checkpoint(case_id, "appeal_writer") or {}
        writer_state["letter"] = letter
        save_checkpoint(case_id, "appeal_writer", writer_state)
        emit("judge", "Judge is reviewing the evidence-corrected final letter", 98, "running")
        with _timed("Final evidence review"):
            judge_result = validate_agent_output(
                "Judge", judge.run(letter, auditor_result, irdai_result, case_id)
            )
        score = judge_result.get("overall_score", 0)
        recommendation = judge_result.get("recommendation", "REVISE")
        if score < MIN_APPROVE_SCORE and recommendation == "APPROVE":
            recommendation = "REVISE"

    if not evidence_validation.valid:
        print(
            f"\n  Evidence validation: {len(evidence_validation.issues)} "
            "unsupported claim(s) found; output marked as invalid"
        )
        recommendation = "VALIDATION_ERROR"
        emit("evidence_validation", "Appeal contains unsupported claims", 98, "error")
    else:
        print("\n  Evidence validation: passed")
        emit("evidence_validation", "Appeal grounded in supplied sources", 98, "done")

    coverage_stages = {
        "auditor": auditor_result.get("input_coverage", {}),
        "policy_analyst": policy_result.get("input_coverage", {}),
    }
    input_coverage = {
        "requires_manual_review": any(c.get("requires_manual_review", False) for c in coverage_stages.values()),
        "stages": coverage_stages,
    }
    review_reasons = list(policy_result.get("policy_review_reasons", []))
    if review_reasons and recommendation == "APPROVE":
        recommendation = "REVIEW_REQUIRED"
    if regulatory_text:
        review_reasons.append("Caller-supplied regulatory text is unverified and was excluded from authoritative evidence.")
        if recommendation == "APPROVE":
            recommendation = "REVIEW_REQUIRED"
    if input_coverage["requires_manual_review"]:
        review_reasons.append("Some source sections were omitted from agent context; review full documents.")
        if recommendation == "APPROVE":
            recommendation = "REVIEW_REQUIRED"

    regulatory_evidence = irdai_result.get("regulatory_evidence", {})
    if regulatory_evidence.get("requires_manual_review"):
        review_reasons.append("Regulatory source provenance is verified; case-specific legal applicability needs human review.")
        if recommendation == "APPROVE":
            recommendation = "REVIEW_REQUIRED"

    # ── Assemble full report ──────────────────────────────────────
    pipeline_time = time.time() - pipeline_start
    llm_stats = get_stats()
    full_report = {
        "case_id": case_id,
        "inputs": {
            "denial_pdf": denial_pdf,
            "policy_pdf": policy_pdf,
        },
        "source_evidence": {"denial": denial_text, "policy": policy_text, "regulatory": irdai_result.get("verified_source_context", "")},
        "policy_evidence": policy_result.get("policy_evidence", []),
        "auditor": auditor_result,
        "policy_analyst": policy_result,
        "irdai_checker": irdai_result,
        "judge": judge_result,
        "appeal_letter": letter,
        "evidence_validation": evidence_validation.as_dict(),
        "quality_issues": ([{"type": "policy_evidence_missing", "message": reason} for reason in policy_result.get("policy_review_reasons", [])] + [{"type": issue.category, "value": issue.value, "message": issue.message} for issue in evidence_validation.issues]),
        "input_coverage": input_coverage,
        "review_reasons": review_reasons,
        "regulatory_evidence": regulatory_evidence,
        "pipeline_stats": {
            "total_time_seconds": round(pipeline_time, 2),
            "revision_count": revision_count,
            "final_score": score,
            "final_recommendation": recommendation,
            "llm_stats": llm_stats,
        },
    }

    output_dir = save_final_output(case_id, letter, full_report)

    print(f"\n{'='*60}")
    print(f"  ✅  Pipeline complete!")
    print(f"  Time          : {pipeline_time:.1f}s")
    print(f"  LLM calls     : {llm_stats['total_calls']}")
    print(f"  Revisions     : {revision_count}")
    print(f"  Final score   : {score:.2f}/1.00")
    print(f"  Output saved  : {output_dir}")
    print(f"  Appeal letter : {output_dir / 'appeal_letter.txt'}")
    print(f"  Full report   : {output_dir / 'full_report.json'}")
    print(f"{'='*60}\n")

    emit("complete", "Pipeline complete", 100, "done")

    return full_report
