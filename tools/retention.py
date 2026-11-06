"""Explicit operator-only retention; preview is the default."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.job_store import JobStore
from tools.review_store import ReviewStore
from tools.case_lifecycle import retention_candidates, delete_case
from tools import io_utils


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--days", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    store = JobStore(args.db)
    jobs = retention_candidates(store, args.days)
    print(json.dumps({"apply": args.apply, "eligible_jobs": jobs}))
    if args.apply:
        reviews = ReviewStore(store.db_path)
        roots = {"sessions": io_utils.SESSIONS_DIR, "outputs": io_utils.OUTPUT_DIR, "inputs": io_utils.PROJECT_ROOT / "data/job_inputs"}
        for job in jobs: delete_case(store, reviews, job["id"], roots)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
