"""
IO Utilities
Handles checkpoint persistence, session tracking, and output saving.
Checkpoints let the pipeline resume from where it left off — 
so if the Gemini API times out mid-run, you don't restart from zero.
"""

import json
import os
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_ROOT / "sessions"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

SESSIONS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


def get_checkpoint_path(case_id: str, stage: str) -> Path:
    session_dir = SESSIONS_DIR / case_id
    session_dir.mkdir(exist_ok=True)
    return session_dir / f"{stage}.json"


def save_checkpoint(case_id: str, stage: str, data: dict) -> None:
    """Save agent output so the pipeline can resume if interrupted."""
    path = get_checkpoint_path(case_id, stage)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[checkpoint] Saved: {path}")


def load_checkpoint(case_id: str, stage: str) -> dict | None:
    """Load a previous agent output if it exists."""
    path = get_checkpoint_path(case_id, stage)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[checkpoint] Loaded existing: {path}")
        return data
    return None


def save_final_output(case_id: str, appeal_letter: str, full_report: dict) -> Path:
    """Save the final appeal letter and full JSON report to output directory."""
    out_dir = create_output_dir(case_id)

    # Plain text appeal letter
    letter_path = out_dir / "appeal_letter.txt"
    with open(letter_path, "w", encoding="utf-8") as f:
        f.write(appeal_letter)

    # Full JSON report with all agent outputs
    report_path = out_dir / "full_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False)

    print(f"\n[output] Appeal letter saved: {letter_path}")
    print(f"[output] Full report saved: {report_path}")
    return out_dir


def create_output_dir(case_id: str) -> Path:
    """Create and return a timestamped output directory for a case."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_DIR / f"{case_id}_{timestamp}"
    out_dir.mkdir(exist_ok=True, parents=True)
    return out_dir


def clear_session(case_id: str) -> None:
    """Delete all checkpoints for a case — forces a full re-run."""
    session_dir = SESSIONS_DIR / case_id
    if session_dir.exists():
        import shutil
        shutil.rmtree(session_dir)
        print(f"[checkpoint] Session cleared: {case_id}")
