"""Content-free lifecycle controls and confined case cleanup.

Secure-delete pragmas and file removal are not guaranteed erasure on SSDs or
backups. Operators must configure encrypted storage and backup retention.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
import stat


def confined_path(root, candidate):
    root = Path(root).resolve()
    candidate = Path(candidate).absolute()
    try:
        relative = candidate.relative_to(root)
        if not relative.parts or any(part in {".", ".."} for part in relative.parts):
            raise ValueError()
        current = root
        for part in relative.parts:
            current = current / part
            attributes = getattr(current.lstat(), "st_file_attributes", 0) if current.exists() or current.is_symlink() else 0
            if current.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024) or getattr(current, "is_junction", lambda: False)():
                raise ValueError()
        candidate.resolve().relative_to(root)
    except ValueError:
        raise ValueError("Unsafe case cleanup path") from None
    return candidate


def delete_case(store, reviews, job_id, roots):
    snapshot = store.begin_delete(job_id)
    case_id = snapshot["case_id"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", case_id) or case_id in {".", ".."}:
        raise ValueError("Unsafe case cleanup path")
    targets = [confined_path(roots["sessions"], Path(roots["sessions"]) / case_id), confined_path(roots["inputs"], Path(roots["inputs"]) / job_id)]
    output_root = Path(roots["outputs"]).resolve()
    artifact = (snapshot.get("result") or {}).get("artifacts", {}).get("output_dir")
    if artifact:
        target = confined_path(output_root, artifact)
        if target.parent != output_root or not target.name.startswith(case_id + "_"):
            raise ValueError("Unsafe case cleanup path")
        targets.append(target)
    # Include outputs created by a cancelled/failed pipeline before a report was persisted.
    if output_root.exists():
        targets.extend(confined_path(output_root, path) for path in output_root.glob(case_id + "_*"))
    reviews.delete(job_id)  # Permanent content-free fence before private cleanup.
    for target in dict.fromkeys(targets):
        if target.is_dir(): shutil.rmtree(target)
        elif target.exists(): raise ValueError("Expected a case directory path")
    store.finish_delete(job_id)


def retention_candidates(store, days):
    if type(days) is not int or days < 1:
        raise ValueError("Retention days must be a positive integer")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store._connect() as db:
        return [dict(row) for row in db.execute("SELECT id,status,updated_at FROM jobs WHERE owner_id IS NOT NULL AND status IN ('completed','failed','cancelled','timed_out','deleting') AND updated_at < ? ORDER BY updated_at", (cutoff,))]
