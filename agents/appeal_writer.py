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
You are a senior insurance lawyer in India with 20 years of experience
writing appeal letters against rejected health insurance claims.
Your letters are:
- Formal and professional in tone
- Specific — they cite exact clauses, IRDAI regulations, and case facts
- Factual — no emotional language, just legal and clinical arguments
- Structured — clearly organised with numbered points
- Effective — your appeal letters have a high reversal rate
You write for Indian insurers, citing IRDAI rules, not US/UK law.
"""


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

Use formal Indian legal correspondence style.
Be specific — cite exact clause numbers and IRDAI regulation names.
Do not use emotional language.
Write [POLICYHOLDER NAME], [DATE], [INSURER ADDRESS] as placeholders where information is missing.
"""

    letter = call_llm(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.3)
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
"""

    revised_letter = call_llm(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.3)

    # Save as revision checkpoint
    checkpoint_key = f"appeal_writer_v{revision_number + 1}"
    save_checkpoint(case_id, checkpoint_key, {"letter": revised_letter})

    # Also update the main checkpoint
    save_checkpoint(case_id, "appeal_writer", {"letter": revised_letter})

    print(f"[Appeal Writer] ✓ Revision #{revision_number} done")
    return revised_letter
