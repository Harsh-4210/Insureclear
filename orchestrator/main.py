"""
Orchestrator — Main Pipeline
Runs all 5 agents in sequence with revision loop.
Handles checkpointing (resume from last successful stage),
timing, validation, and assembles the final output package.
"""

import sys
import time
from typing import Callable, Any
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.pdf_reader import extract_text_from_pdf
from tools.io_utils import save_final_output
from tools.llm_client import get_stats
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
) -> dict:
    """
    Full pipeline: PDF inputs → appeal letter + scorecard.

    Args:
        denial_pdf: Path to the rejection letter PDF
        policy_pdf: Path to the insurance policy PDF
        case_id: Unique ID for this case (used for checkpointing)
        denial_text: Pre-extracted denial text (skips PDF reading if provided)
        policy_text: Pre-extracted policy text (skips PDF reading if provided)

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

    # ── Agent 1: Auditor ──────────────────────────────────────────
    print("\n[Step 1/5] Auditor — Parsing documents...")
    emit("auditor", "Auditor is parsing denial and policy documents", 15, "running")
    with _timed("Auditor") as t1:
        auditor_result = auditor.run(denial_text, policy_text, case_id)

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

    valid = policy_result.get("rejection_appears_valid")
    print(f"\n  Rejection legitimacy: {'⚠️  Appears valid' if valid else '✓ Challengeable'}")

    # ── Agent 3: IRDAI Checker ────────────────────────────────────
    print("\n[Step 3/5] IRDAI Checker — Checking against regulations...")
    emit("irdai_checker", "IRDAI Checker is matching the case against regulations", 50, "running")
    with _timed("IRDAI Checker") as t3:
        irdai_result = irdai_checker.run(auditor_result, policy_result, case_id)

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
    print(f"  Letter length: {len(letter.split())} words")

    # ── Agent 5: Judge ────────────────────────────────────────────
    print("\n[Step 5/5] Judge — Reviewing quality...")
    emit("judge", "Judge is reviewing the draft for quality and hallucinations", 85, "running")
    with _timed("Judge") as t5:
        judge_result = judge.run(letter, auditor_result, irdai_result, case_id)

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

        # Clear judge checkpoint so it re-evaluates the revised letter
        from tools.io_utils import get_checkpoint_path
        judge_cp = get_checkpoint_path(case_id, "judge")
        if judge_cp.exists():
            judge_cp.unlink()

        # Re-judge the revised letter
        print(f"\n  [Judge] Re-evaluating revision #{revision_count}...")
        with _timed(f"Judge re-evaluation #{revision_count}"):
            judge_result = judge.run(letter, auditor_result, irdai_result, case_id)

        score = judge_result.get("overall_score", 0)
        recommendation = judge_result.get("recommendation", "APPROVE")

        if score < MIN_APPROVE_SCORE and recommendation == "APPROVE":
            recommendation = "REVISE"

        print(f"\n  Revised score : {score:.2f}/1.00")
        print(f"  Recommendation: {recommendation}")
        emit("revision_review", f"Revision #{revision_count} scored {score:.2f}", 95, "running")

    if revision_count > 0:
        print(f"\n  Total revisions: {revision_count}")

    # ── Assemble full report ──────────────────────────────────────
    pipeline_time = time.time() - pipeline_start
    llm_stats = get_stats()

    full_report = {
        "case_id": case_id,
        "inputs": {
            "denial_pdf": denial_pdf,
            "policy_pdf": policy_pdf,
        },
        "auditor": auditor_result,
        "policy_analyst": policy_result,
        "irdai_checker": irdai_result,
        "judge": judge_result,
        "appeal_letter": letter,
        "artifacts": {
            "output_dir": str(output_dir),
            "appeal_letter_path": str(output_dir / "appeal_letter.txt"),
            "full_report_path": str(output_dir / "full_report.json"),
        },
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
