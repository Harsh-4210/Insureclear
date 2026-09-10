"""
CLI Interface
Run the full pipeline from the terminal.

Usage:
    python orchestrator/cli.py --denial data/input/denial.pdf --policy data/input/policy.pdf
    python orchestrator/cli.py --denial data/input/denial.pdf --policy data/input/policy.pdf --case my_case_001
    python orchestrator/cli.py --demo
    python orchestrator/cli.py --text-denial denial.txt --text-policy policy.txt
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.main import run_pipeline
from tools.io_utils import clear_session

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"


def main():
    parser = argparse.ArgumentParser(
        description="InsureClear — Indian Health Insurance Appeal Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full run with PDFs
  python orchestrator/cli.py --denial data/input/denial.pdf --policy data/input/policy.pdf

  # Named case (enables resume-from-checkpoint)
  python orchestrator/cli.py --denial data/input/denial.pdf --policy data/input/policy.pdf --case case_001

  # Demo mode — uses built-in sample data (no PDFs needed)
  python orchestrator/cli.py --demo

  # Text file input (skips PDF extraction)
  python orchestrator/cli.py --text-denial denial.txt --text-policy policy.txt

  # Force fresh run
  python orchestrator/cli.py --demo --fresh
        """
    )

    parser.add_argument(
        "--denial",
        help="Path to the claim rejection letter PDF"
    )
    parser.add_argument(
        "--policy",
        help="Path to the insurance policy document PDF"
    )
    parser.add_argument(
        "--text-denial",
        help="Path to denial letter as plain text (skips PDF extraction)"
    )
    parser.add_argument(
        "--text-policy",
        help="Path to policy document as plain text (skips PDF extraction)"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run with built-in sample data — no PDFs needed"
    )
    parser.add_argument(
        "--case", default=None,
        help="Case ID for checkpointing (auto-generated if not provided)"
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Force a fresh run — ignores existing checkpoints"
    )

    args = parser.parse_args()

    # Determine input mode
    denial_text = None
    policy_text = None
    denial_pdf = "demo"
    policy_pdf = "demo"

    if args.demo:
        # Demo mode — use built-in sample data
        print("\n🎯 Demo mode — using built-in sample denial and policy")
        denial_file = SAMPLES_DIR / "sample_denial.txt"
        policy_file = SAMPLES_DIR / "sample_policy.txt"

        if not denial_file.exists() or not policy_file.exists():
            print("Error: Sample files not found in data/samples/")
            print("Expected: sample_denial.txt, sample_policy.txt")
            sys.exit(1)

        denial_text = denial_file.read_text(encoding="utf-8")
        policy_text = policy_file.read_text(encoding="utf-8")
        denial_pdf = str(denial_file)
        policy_pdf = str(policy_file)

    elif args.text_denial and args.text_policy:
        # Text file input mode
        denial_path = Path(args.text_denial)
        policy_path = Path(args.text_policy)

        if not denial_path.exists():
            print(f"Error: Denial text file not found: {args.text_denial}")
            sys.exit(1)
        if not policy_path.exists():
            print(f"Error: Policy text file not found: {args.text_policy}")
            sys.exit(1)

        denial_text = denial_path.read_text(encoding="utf-8")
        policy_text = policy_path.read_text(encoding="utf-8")
        denial_pdf = str(denial_path)
        policy_pdf = str(policy_path)

    elif args.denial and args.policy:
        # PDF mode
        if not Path(args.denial).exists():
            print(f"Error: Denial PDF not found: {args.denial}")
            sys.exit(1)
        if not Path(args.policy).exists():
            print(f"Error: Policy PDF not found: {args.policy}")
            sys.exit(1)

        denial_pdf = args.denial
        policy_pdf = args.policy

    else:
        print("Error: Provide either --demo, --denial + --policy, or --text-denial + --text-policy")
        parser.print_help()
        sys.exit(1)

    case_id = args.case or f"case_{uuid.uuid4().hex[:8]}"

    if args.fresh:
        clear_session(case_id)

    try:
        run_pipeline(
            denial_pdf=denial_pdf,
            policy_pdf=policy_pdf,
            case_id=case_id,
            denial_text=denial_text,
            policy_text=policy_text,
        )
    except EnvironmentError as e:
        print(f"\n❌  Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌  Pipeline error: {e}")
        raise


if __name__ == "__main__":
    main()
