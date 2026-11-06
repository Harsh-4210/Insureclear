"""
IO Utilities
Handles checkpoint persistence, session tracking, and output saving.
Checkpoints let the pipeline resume from where it left off — 
so if the Gemini API times out mid-run, you don't restart from zero.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_ROOT / "sessions"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

SESSIONS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


def _session_directory(case_id: str) -> Path:
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", case_id):
        raise ValueError("case_id contains unsupported characters")
    root = SESSIONS_DIR.resolve()
    session_dir = (root / case_id).resolve()
    if session_dir.parent != root:
        raise ValueError("case_id must resolve inside the sessions directory")
    return session_dir


def get_checkpoint_path(case_id: str, stage: str) -> Path:
    session_dir = _session_directory(case_id)
    if not re.fullmatch(r"[A-Za-z0-9_]+", stage):
        raise ValueError("Unsupported checkpoint stage")
    session_dir.mkdir(exist_ok=True, parents=True)
    return session_dir / f"{stage}.json"


def prepare_session(case_id: str, denial_text: str, policy_text: str, regulatory_text: str | None, context_fingerprint: str = "") -> None:
    """Reuse checkpoints only when every source and the cache version match."""
    sources = json.dumps([3, denial_text, policy_text, regulatory_text or "", context_fingerprint], ensure_ascii=False)
    fingerprint = hashlib.sha256(sources.encode("utf-8")).hexdigest()
    expected = {"input_sha256": fingerprint}
    try:
        existing = load_checkpoint(case_id, "inputs")
    except (json.JSONDecodeError, UnicodeDecodeError):
        existing = None
    if existing != expected:
        clear_session(case_id)
        save_checkpoint(case_id, "inputs", expected)


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
    full_report["artifacts"] = {
        "output_dir": str(out_dir),
        "appeal_letter_path": str(out_dir / "appeal_letter.txt"),
        "full_report_path": str(out_dir / "full_report.json"),
    }

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
    _session_directory(case_id)  # Validate the same case namespace used by checkpoints.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_dir = OUTPUT_DIR / f"{case_id}_{timestamp}"
    out_dir.mkdir(exist_ok=True, parents=True)
    return out_dir


def clear_session(case_id: str) -> None:
    """Delete all checkpoints for a case — forces a full re-run."""
    session_dir = _session_directory(case_id)
    if session_dir.exists():
        import shutil
        shutil.rmtree(session_dir)
        print(f"[checkpoint] Session cleared: {case_id}")
