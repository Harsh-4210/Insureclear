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
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from eval.cases import CASES, build_documents
from eval.score import score_case, summarise
from orchestrator.main import run_pipeline
from tools import llm_client
from tools.io_utils import clear_session
from tools.regulatory_registry import load_registry

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



def evaluation_sources(denial: str, policy: str, report: dict) -> list[str]:
    """Reconstruct support from pinned source bytes, never model-provided text."""
    sources = [denial, policy]
    metadata = report.get("regulatory_evidence") or {}
    if not metadata:
        return sources
    registry = load_registry()
    if metadata.get("registry_fingerprint") != registry.fingerprint:
        raise ValueError("Evaluation registry version differs from the report; use its pinned registry")
    allowed = {f"{c['source_id']}:{c['id']}": c for c in registry.clauses}
    for entry in metadata.get("excerpts", []):
        evidence_id = entry.get("evidence_id")
        clause = allowed.get(evidence_id) if isinstance(evidence_id, str) else None
        if not clause or entry.get("text") != clause["text"]:
            raise ValueError("Evaluation source excerpt failed pinned-registry integrity")
        source = registry.sources[clause["source_id"]]
        sources.append(source["reference"] + "\n" + clause["text"])
    return sources


def _tick(value) -> str:
    return "yes" if value else "no"


def write_summary(run_dir: Path, results: list[dict], failures: list[dict], reused_cases: int = 0) -> dict:
    summary = summarise(results)
    summary["reused_cases"] = reused_cases
    summary["new_cases"] = len(results) - reused_cases
    summary["usage_scope"] = "current_invocation"
    summary["failed_cases"] = len(failures)
    summary["failures"] = failures
    summary["model"] = f"{llm_client.PROVIDER}:{llm_client.MODEL_NAME}"
    summary["reasoning_effort"] = llm_client.GROQ_REASONING_EFFORT if llm_client.PROVIDER == "groq" else None
    summary["total_tokens"] = llm_client.get_stats()["total_tokens"]
    llm_stats = llm_client.get_stats()
    summary["llm_calls"] = llm_stats["total_calls"]
    summary["llm_retries"] = llm_stats["total_retries"]
    summary["llm_429s"] = llm_stats["total_429s"]
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        f"# InsureClear evaluation ({run_dir.name})",
        "",
        f"Model: `{summary['model']}`. Cases: {summary['cases']} synthetic denials with a hand-written answer key.",
        "",
        f"Reports: {summary['reused_cases']} reused and reverified; {summary['new_cases']} newly generated. Provider usage counts this invocation only.",
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
            f"- Verdict accuracy: {summary['verdict_accuracy']:.0%}",
            f"- Letter fact accuracy: {summary['letter_fact_accuracy']:.0%}",
            f"- Winning argument made: {summary['key_argument_found']}/{summary['key_argument_cases']}",
            f"- Cases with unsupported claims: {summary['letters_with_unsupported_ids']}/{summary['cases']} "
            f"({summary['unsupported_claim_rate']:.0%})",
            f"- Mean judge score: {summary['mean_judge_score']}, mean revisions: {summary['mean_revisions']}, "
            f"mean time per case: {summary['mean_seconds']}s",
            f"- Failed cases: {summary['failed_cases']}",
            f"- LLM calls: {summary['llm_calls']}, retries: {summary['llm_retries']}, 429s: {summary['llm_429s']}",
        ]
    if failures:
        lines += ["", "## Failures", "", "| Case | Error |", "|---|---|"]
        lines.extend(f"| {failure['id']} | {failure['error']} |" for failure in failures)
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def check_regression_gates(
    summary: dict,
    min_verdict_accuracy: float | None = None,
    max_unsupported_claim_rate: float | None = None,
) -> list[str]:
    """Return CI-friendly gate failures without raising or hiding the report."""
    failures = []
    if min_verdict_accuracy is not None and summary.get("verdict_accuracy", 0) < min_verdict_accuracy:
        failures.append(
            f"verdict accuracy {summary.get('verdict_accuracy', 0):.3f} "
            f"is below {min_verdict_accuracy:.3f}"
        )
    if max_unsupported_claim_rate is not None and summary.get("unsupported_claim_rate", 0) > max_unsupported_claim_rate:
        failures.append(
            f"unsupported claim rate {summary.get('unsupported_claim_rate', 0):.3f} "
            f"exceeds {max_unsupported_claim_rate:.3f}"
        )
    if summary.get("failed_cases", 0):
        failures.append(f"{summary['failed_cases']} case(s) failed to run")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the InsureClear evaluation")
    parser.add_argument("--only", nargs="*", help="Run only cases whose id starts with these prefixes")
    parser.add_argument("--resume", help="Existing run id to continue")
    parser.add_argument(
        "--min-verdict-accuracy", type=float,
        default=float(os.environ["EVAL_MIN_VERDICT_ACCURACY"])
        if os.environ.get("EVAL_MIN_VERDICT_ACCURACY") else None,
        help="Fail (exit 1) when verdict accuracy is below this value",
    )
    parser.add_argument(
        "--max-unsupported-claim-rate", type=float,
        default=float(os.environ["EVAL_MAX_UNSUPPORTED_CLAIM_RATE"])
        if os.environ.get("EVAL_MAX_UNSUPPORTED_CLAIM_RATE") else None,
        help="Fail (exit 1) when unsupported-claim case rate exceeds this value",
    )
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
    reused_cases = 0
    for case in cases:
        case_file = run_dir / f"{case['id']}.json"
        if case_file.exists():
            saved = json.loads(case_file.read_text(encoding="utf-8"))
            denial, policy = build_documents(case)
            try:
                score = score_case(saved["report"], case, evaluation_sources(denial, policy, saved["report"]))
            except (ValueError, KeyError, TypeError) as error:
                failures.append({"id": case["id"], "error": str(error), "exception_type": type(error).__name__})
                print(f"[eval] {case['id']}: saved report cannot be verified: {error}")
                continue
            if saved.get("score") != score:
                saved.setdefault("score_history", []).append(saved.get("score"))
                saved["score"] = score
                saved["score_schema_version"] = 2
                case_file.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
            results.append(score)
            reused_cases += 1
            print(f"[eval] {case['id']}: saved report verified and rescored, no provider call")
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

        score = score_case(report, case, evaluation_sources(denial, policy, report))
        case_file.write_text(
            json.dumps({"score": score, "report": report, "score_schema_version": 2}, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        results.append(score)
        print(f"[eval] {case['id']}: scored")
        time.sleep(2)

    summary = write_summary(run_dir, results, failures, reused_cases)
    print(json.dumps(summary, indent=2))
    print(f"\nResults: {run_dir}")
    gate_failures = check_regression_gates(
        summary, args.min_verdict_accuracy, args.max_unsupported_claim_rate
    )
    if gate_failures:
        print("[eval] regression gate failed: " + "; ".join(gate_failures), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
