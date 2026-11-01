"""
Evaluation Runner
Runs the real pipeline (live Gemini calls) on every case in eval/cases.py,
scores each report with eval/score.py, and writes:

  eval/results/<run_id>/<case_id>.json   full report + scores per case
  eval/results/<run_id>/summary.json     totals
  eval/results/<run_id>/summary.md       readable table

Usage:
  python eval/run_eval.py                 # all cases
  python eval/run_eval.py --only c01 c05  # cases whose id starts with these
  python eval/run_eval.py --resume <run_id>  # skip cases already scored
"""

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from eval.cases import CASES, build_documents
from eval.score import score_case, summarise
from orchestrator.main import run_pipeline
from tools import llm_client
from tools.io_utils import clear_session

RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
MIN_SECONDS_BETWEEN_CALLS = 13  # Gemini free tier allows 5 requests per minute


def _throttle_gemini() -> None:
    """
    Space out Gemini calls and wait out 429s, so the free tier's per-minute
    limit does not fail a case. Only affects this evaluation run.
    Groq needs nothing here: the client already waits for Groq's retry-after.
    """
    if llm_client.PROVIDER != "gemini":
        return
    model_cls = llm_client.genai.GenerativeModel
    original = model_cls.generate_content
    last_call = [0.0]

    def throttled(self, *args, **kwargs):
        for attempt in range(6):
            wait = MIN_SECONDS_BETWEEN_CALLS - (time.time() - last_call[0])
            if wait > 0:
                time.sleep(wait)
            last_call[0] = time.time()
            try:
                return original(self, *args, **kwargs)
            except Exception as e:
                if "429" not in str(e) or attempt == 5:
                    raise
                print("[eval] Gemini rate limit, waiting 60s")
                time.sleep(60)

    model_cls.generate_content = throttled
KNOWLEDGE_TEXT = (PROJECT_ROOT / "tools" / "irdai_knowledge.py").read_text(encoding="utf-8")


def _tick(value) -> str:
    return "yes" if value else "no"


def write_summary(run_dir: Path, results: list[dict], failures: list[dict]) -> dict:
    summary = summarise(results)
    summary["failed_cases"] = len(failures)
    summary["failures"] = failures
    summary["model"] = f"{llm_client.PROVIDER}:{llm_client.MODEL_NAME}"
    summary["reasoning_effort"] = llm_client.GROQ_REASONING_EFFORT if llm_client.PROVIDER == "groq" else None
    summary["total_tokens"] = llm_client.get_stats()["total_tokens"]
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        f"# InsureClear evaluation ({run_dir.name})",
        "",
        f"Model: `{summary['model']}`. Cases: {summary['cases']} synthetic denials with a hand-written answer key.",
        "",
        "| Case | Facts extracted | Verdict right | Letter facts | Key argument | Unsupported IDs | Judge | Revisions |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        arg = "n/a" if not r["key_argument"]["applicable"] else _tick(r["key_argument"]["found"])
        lines.append(
            f"| {r['id']} | {r['extraction']['score']:.2f} | {_tick(r['verdict']['correct'])} "
            f"| {r['letter_facts']['score']:.2f} | {arg} | {', '.join(r['unsupported_ids']) or '-'} "
            f"| {r['judge_final_score']} | {r['revisions']} |"
        )
    if summary["cases"]:
        lines += [
            "",
            f"- Fact extraction accuracy: {summary['extraction_accuracy']:.0%}",
            f"- Correct valid/challengeable verdict: {summary['verdict_correct']}/{summary['cases']}",
            f"- Letter fact accuracy: {summary['letter_fact_accuracy']:.0%}",
            f"- Winning argument made: {summary['key_argument_found']}/{summary['key_argument_cases']}",
            f"- Letters with an unsupported reference number: {summary['letters_with_unsupported_ids']}/{summary['cases']}",
            f"- Mean judge score: {summary['mean_judge_score']}, mean revisions: {summary['mean_revisions']}, "
            f"mean time per case: {summary['mean_seconds']}s",
            f"- Failed cases: {summary['failed_cases']}",
        ]
    if failures:
        lines += ["", "## Failures", "", "| Case | Error |", "|---|---|"]
        lines.extend(f"| {failure['id']} | {failure['error']} |" for failure in failures)
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the InsureClear evaluation")
    parser.add_argument("--only", nargs="*", help="Run only cases whose id starts with these prefixes")
    parser.add_argument("--resume", help="Existing run id to continue")
    args = parser.parse_args()
    _throttle_gemini()

    run_id = args.resume or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cases = CASES
    if args.only:
        cases = [c for c in CASES if any(c["id"].startswith(p) for p in args.only)]

    results = []
    failures = []
    for case in cases:
        case_file = run_dir / f"{case['id']}.json"
        if case_file.exists():
            results.append(json.loads(case_file.read_text(encoding="utf-8"))["score"])
            print(f"[eval] {case['id']}: already scored, skipping")
            continue

        denial, policy = build_documents(case)
        case_id = f"eval_{run_id}_{case['id']}"
        try:
            report = run_pipeline(
                denial_pdf="(eval text)",
                policy_pdf="(eval text)",
                case_id=case_id,
                denial_text=denial,
                policy_text=policy,
            )
        except Exception as e:
            print(f"[eval] {case['id']}: pipeline failed: {e}")
            failure = {
                "id": case["id"],
                "error": str(e),
                "exception_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            }
            failures.append(failure)
            (run_dir / f"{case['id']}.error.txt").write_text(
                json.dumps(failure, indent=2), encoding="utf-8"
            )
            continue
        finally:
            clear_session(case_id)

        score = score_case(report, case, [denial, policy, KNOWLEDGE_TEXT])
        case_file.write_text(
            json.dumps({"score": score, "report": report}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        results.append(score)
        print(f"[eval] {case['id']}: scored")
        time.sleep(2)

    summary = write_summary(run_dir, results, failures)
    print(json.dumps(summary, indent=2))
    print(f"\nResults: {run_dir}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
