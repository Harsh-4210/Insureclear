"""
Agent 4: Appeal Writer
Composes a professional, legally grounded appeal letter.
Draws on all three previous agents' outputs.
Written in formal Indian legal correspondence style.
Supports revision based on Judge feedback.
"""

from tools.llm_client import call_llm
from tools.io_utils import save_checkpoint, load_checkpoint

SYSTEM_PROMPT = """
You are an insurance appeal drafting assistant for Indian health insurance
claims. You are not a lawyer and must not present uncertain research as settled
law.
Your letters are:
- Formal and professional in tone
- Specific — they cite exact clauses, IRDAI regulations, and case facts
- Factual — no emotional language, just legal and clinical arguments
- Structured — clearly organised with numbered points
- Careful — unsupported legal claims are worse than a clearly labelled argument
You write for Indian insurers, citing IRDAI rules, not US/UK law.
"""


def _valid_denial_posture(policy_analyst_output: dict) -> str:
    if policy_analyst_output.get("rejection_appears_valid") is True:
        return """
VALID-DENIAL GUARDRAIL (mandatory):
The policy analysis says the rejection appears valid. Draft a review-and-explanation
request, not an aggressive appeal. Do not accuse the insurer of an IRDAI violation.
Treat every regulatory concern and escalation route as a review lead requiring manual
verification. Ask the insurer to confirm the clause, calculations, and reasons, and
make escalation conditional on an unsatisfactory explanation or new evidence.
Use only dates, amounts, names, identifiers, and clauses explicitly present in the
claim facts or policy findings. Do not invent hospitalisation dates, diagnoses,
medical records, statutory deadlines, circular numbers, case law, or evidence of
disclosure. If a fact is missing, ask the insurer to provide it.
"""
    return ""


def _enforce_valid_denial_posture(
    letter: str, policy_analyst_output: dict, irdai_output: dict | None = None
) -> str:
    """Add a deterministic, non-accusatory framing if the model omitted it."""
    valid = policy_analyst_output.get("rejection_appears_valid") is True
    if not valid or "review and explanation" in letter.lower():
        return letter
    notice = (
        "Posture: This is a request for review and explanation because the policy "
        "analysis indicates that the rejection appears valid. Regulatory concerns "
        "are not asserted as violations; any escalation should depend on the "
        "insurer's explanation or new evidence.\n\n"
    )
    return notice + letter


def run(
    auditor_output: dict,
    policy_analyst_output: dict,
    irdai_output: dict,
    case_id: str,
) -> str:
    """
    Write the appeal letter.
    Returns the full letter as a string.
    """
    cached = load_checkpoint(case_id, "appeal_writer")
    if cached:
        return cached.get("letter", "")

    print("\n[Appeal Writer] Drafting appeal letter...")

    # Gather strongest arguments
    counter_args = policy_analyst_output.get("strongest_counter_arguments", [])
    legal_points = irdai_output.get("key_legal_points_for_appeal", [])
    violations = irdai_output.get("potential_insurer_violations", [])
    docs_to_attach = irdai_output.get("what_documents_to_attach", [])
    posture = _valid_denial_posture(policy_analyst_output)

    prompt = f"""
Write a formal insurance appeal letter using these details:

CLAIM FACTS:
- Insurer: {auditor_output.get('insurer_name')}
- Policy Number: {auditor_output.get('policy_number')}
- Claim Number: {auditor_output.get('claim_number')}
- Policyholder: {auditor_output.get('policyholder_name')}
- Treatment: {auditor_output.get('treatment_or_procedure')}
- Hospital: {auditor_output.get('hospital_name')}
- Claim Amount: {auditor_output.get('claim_amount')}
- Date of Denial: {auditor_output.get('denial_date')}
- Insurer's Stated Reason: {auditor_output.get('denial_reason_verbatim')}
- Clause Cited by Insurer: {auditor_output.get('policy_clause_cited')}

POLICY ANALYSIS FINDINGS:
- Rejection appears valid: {policy_analyst_output.get('rejection_appears_valid')}
- Explanation: {policy_analyst_output.get('rejection_validity_explanation')}
- Counter arguments: {counter_args}
- Ambiguous policy wording: {policy_analyst_output.get('policy_wording_ambiguity')}

IRDAI LEGAL POINTS:
- Key legal points: {legal_points}
- Potential violations by insurer: {violations}
- Recommended appeal pathway: {irdai_output.get('appeal_pathway', {}).get('recommended_first_step')}

DOCUMENTS TO ATTACH: {docs_to_attach}

Write a complete, formal appeal letter. Structure it as:
1. Header (date, addresses, subject line)
2. Introduction — brief statement of the appeal
3. Background — facts of the case
4. Grounds for Appeal — numbered points, each citing specific clauses or IRDAI rules
5. Relief Sought — specific ask
6. Escalation Notice — mention Bima Bharosa and Ombudsman if not resolved in 15 days
7. List of enclosures

Use formal Indian correspondence style.
Be specific — cite exact clause numbers and supplied IRDAI regulation names.
Label citations that require manual verification instead of inventing support.
Do not use emotional language.
Write [POLICYHOLDER NAME], [DATE], [INSURER ADDRESS] as placeholders where information is missing.
{posture}
"""

    letter = call_llm(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.3)
    letter = _enforce_valid_denial_posture(letter, policy_analyst_output, irdai_output)
    save_checkpoint(case_id, "appeal_writer", {"letter": letter})
    print("[Appeal Writer] ✓ Done")
    return letter


def revise(
    original_letter: str,
    judge_feedback: dict,
    auditor_output: dict,
    irdai_output: dict,
    case_id: str,
    revision_number: int = 1,
) -> str:
    """
    Revise the appeal letter based on Judge feedback.
    Returns the revised letter as a string.
    """
    print(f"\n[Appeal Writer] Revising letter (revision #{revision_number})...")

    hallucinations = judge_feedback.get("hallucination_flags", [])
    missing = judge_feedback.get("missing_elements", [])
    weak = judge_feedback.get("weak_arguments", [])
    top_changes = judge_feedback.get("if_revise_top_changes", [])

    prompt = f"""
You previously wrote this insurance appeal letter:

=== ORIGINAL LETTER ===
{original_letter}

A quality reviewer has flagged the following issues:

HALLUCINATIONS (claims not supported by source documents):
{hallucinations}

MISSING ELEMENTS (should be added):
{missing}

WEAK ARGUMENTS (should be strengthened or removed):
{weak}

TOP CHANGES REQUIRED:
{top_changes}

VERIFIED FACTS (use only these):
- Insurer: {auditor_output.get('insurer_name')}
- Policy Number: {auditor_output.get('policy_number')}
- Claim Number: {auditor_output.get('claim_number')}
- Denial reason: {auditor_output.get('denial_reason_verbatim')}
- IRDAI legal points: {irdai_output.get('key_legal_points_for_appeal')}

Rewrite the COMPLETE appeal letter with these fixes applied.
Do NOT add any new facts that aren't in the verified facts above.
Maintain formal Indian legal correspondence style.
If the regulatory output contains conflict_metadata.regulatory_posture =
"review_and_explanation", preserve a review-and-explanation posture and do not
turn regulatory leads into accusations.
"""

    revised_letter = call_llm(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.3)
    revised_letter = _enforce_valid_denial_posture(
        revised_letter,
        {"rejection_appears_valid": irdai_output.get("conflict_metadata", {}).get(
            "rejection_appears_valid", False
        )},
        irdai_output,
    )

    # Save as revision checkpoint
    checkpoint_key = f"appeal_writer_v{revision_number + 1}"
    save_checkpoint(case_id, checkpoint_key, {"letter": revised_letter})

    # Also update the main checkpoint
    save_checkpoint(case_id, "appeal_writer", {"letter": revised_letter})

    print(f"[Appeal Writer] ✓ Revision #{revision_number} done")
    return revised_letter
