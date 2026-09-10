"""
Agent 2: Policy Analyst
Deep-reads the policy document to identify ALL hidden traps:
sub-limits, co-pays, waiting periods, exclusions, network clauses.
Tells the appeal whether the rejection was legitimately applied or not.
"""

from tools.llm_client import call_llm_json
from tools.irdai_knowledge import POLICY_RED_FLAGS
from tools.io_utils import save_checkpoint, load_checkpoint

SYSTEM_PROMPT = """
You are a senior Indian health insurance policy analyst with 15 years of experience.
You specialise in finding clauses that insurers use to reduce or reject claims,
and identifying when those clauses have been wrongly applied.
You know IRDAI regulations deeply.
"""


def run(policy_text: str, auditor_output: dict, case_id: str) -> dict:
    """
    Analyse the policy document in the context of the specific denial.
    Returns findings about whether the rejection was legitimate.
    """
    cached = load_checkpoint(case_id, "policy_analyst")
    if cached:
        return cached

    print("\n[Policy Analyst] Examining policy terms...")

    red_flags_context = "\n".join([
        f"- {k}: {v['description']}" for k, v in POLICY_RED_FLAGS.items()
    ])

    prompt = f"""
A claim has been denied with the following details:
- Treatment: {auditor_output.get('treatment_or_procedure')}
- Denial reason: {auditor_output.get('denial_reason_verbatim')}
- Denial category: {auditor_output.get('denial_reason_category')}
- Clause cited: {auditor_output.get('policy_clause_cited')}
- Policy start date: {auditor_output.get('policy_start_date')}
- Sum insured: {auditor_output.get('sum_insured')}

=== POLICY DOCUMENT ===
{policy_text[:5000]}

Analyse this policy in the context of this denial.

Known policy red flags to look for:
{red_flags_context}

Return a JSON object:
{{
  "room_rent_limit_found": "Room rent sub-limit if found (e.g. '1% of SI per day' or '₹3000/day'), else null",
  "room_rent_limit_applies": true/false,
  "co_pay_clause": "Co-pay clause text if found, else null",
  "co_pay_applies": true/false,
  "relevant_waiting_periods": [
    {{"type": "initial/pre_existing/specific_disease", "duration": "30 days / 2 years / etc", "clause": "clause reference"}}
  ],
  "waiting_period_violation": true/false,
  "waiting_period_explanation": "Why the waiting period does or does not apply here",
  "relevant_exclusions": ["list of exclusions in the policy that are relevant to this claim"],
  "exclusion_validly_applied": true/false,
  "exclusion_analysis": "Detailed explanation of whether the exclusion legitimately applies",
  "policy_wording_ambiguity": "Any vague or ambiguous wording in the policy that could be interpreted in the policyholder's favour",
  "proportionate_deduction_applicable": true/false,
  "proportionate_deduction_explanation": "If room rent was exceeded, explain the proportionate deduction rule",
  "mis_selling_indicators": ["Any signs that the policy was sold without clearly disclosing these terms"],
  "rejection_appears_valid": true/false,
  "rejection_validity_explanation": "Clear explanation of whether the insurer's rejection seems legitimate or challengeable",
  "strongest_counter_arguments": [
    "List the strongest arguments the policyholder can make against this rejection"
  ]
}}
"""

    result = call_llm_json(prompt, system_prompt=SYSTEM_PROMPT)
    save_checkpoint(case_id, "policy_analyst", result)
    print("[Policy Analyst] ✓ Done")
    return result
