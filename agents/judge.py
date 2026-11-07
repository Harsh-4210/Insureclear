"""
Agent 5: Judge
Reviews the generated appeal letter and scores its quality.
Catches weak arguments, missing citations, and hallucinated facts.
Outputs a scorecard and a final APPROVE/REVISE recommendation.
"""

import hashlib
from tools.document_context import EVIDENCE_BOUNDARY, ensure_prompt_budget
from tools.llm_client import call_llm_json, dispatch_padding
from tools.io_utils import save_checkpoint, load_checkpoint

SYSTEM_PROMPT = """
You are a strict quality reviewer of Indian insurance appeal letters.
You evaluate whether an appeal letter is strong enough to succeed.
You check for: factual accuracy, legal citation quality, structural completeness,
and whether the arguments are grounded in the actual documents (not generic claims).
You flag hallucinations — claims made in the letter that are not supported by the source documents.
Do not request a citation, case reference, statutory deadline, medical fact, or policy
detail merely because it would strengthen the letter. Mark it as missing only when
it is present in the supplied facts or source material. Unsupported additions must
be removed or rewritten as a request for the insurer to provide clarification.
""" + "\n" + EVIDENCE_BOUNDARY


def run(
    appeal_letter: str,
    auditor_output: dict,
    irdai_output: dict,
    case_id: str,
) -> dict:
    """
    Score and validate the appeal letter.
    Returns a scorecard dict with recommendation.
    """
    print("\n[Judge] Reviewing and scoring appeal letter...")

    prompt = f"""
Review this insurance appeal letter against the source facts.

=== APPEAL LETTER ===
{appeal_letter}

=== VERIFIED FACTS (from source documents) ===
- Insurer: {auditor_output.get('insurer_name')}
- Policy Number: {auditor_output.get('policy_number')}
- Claim Number: {auditor_output.get('claim_number')}
- Denial reason: {auditor_output.get('denial_reason_verbatim')}
- Clause cited: {auditor_output.get('policy_clause_cited')}
- Policyholder: {auditor_output.get('policyholder_name')}
- Claim amount: {auditor_output.get('claim_amount')}
- Hospital: {auditor_output.get('hospital_name')}
- Treatment: {auditor_output.get('treatment_or_procedure')}
- Denial date: {auditor_output.get('denial_date')}
No generated legal research or estimated success probability is a verified fact.

=== VERIFIED POLICY WORDING ===
{irdai_output.get("verified_policy_context", "No verified policy quotes supplied.")}
Check the main contractual argument and every exception against this wording.
Do not request wording already supplied. Flag unsupported numeric response deadlines.

=== PINNED REGULATORY SOURCE EVIDENCE ===
{irdai_output.get("verified_source_context", "No pinned source excerpts supplied.")}
Source provenance does not establish legal applicability. Verify interpretations
against these exact excerpts; do not treat generated research leads as evidence.

Score the appeal letter on these dimensions (0.0 to 1.0):

Return a JSON object:
{{
  "factual_accuracy": 0.0,
  "factual_accuracy_notes": "Are all stated facts accurate and sourced from actual documents?",
  "irdai_citation_quality": 0.0,
  "irdai_citation_notes": "Are IRDAI regulations cited correctly and relevantly?",
  "argument_strength": 0.0,
  "argument_strength_notes": "Are the counter-arguments legally sound and persuasive?",
  "structure_integrity": 0.0,
  "structure_integrity_notes": "Is the letter professionally structured?",
  "hallucination_flags": [
    "List any claims in the letter that are NOT supported by the source documents"
  ],
  "missing_elements": [
    "List important arguments or citations that should be added but are absent"
  ],
  "weak_arguments": [
    "List arguments in the letter that are weak or unlikely to succeed"
  ],
  "overall_score": 0.0,
  "recommendation": "APPROVE or REVISE",
  "recommendation_reasoning": "Why APPROVE or REVISE",
  "if_revise_top_changes": [
    "If REVISE: the top 3 specific changes to make"
  ]
}}

Score honestly. An overall score above 0.75 = APPROVE. Below 0.75 = REVISE.
"""

    ensure_prompt_budget(prompt, SYSTEM_PROMPT, 2048 + dispatch_padding(True))
    reviewed_hash = hashlib.sha256((SYSTEM_PROMPT + "\n" + prompt).encode()).hexdigest()
    cached = load_checkpoint(case_id, "judge")
    if cached and cached.get("reviewed_context_sha256") == reviewed_hash:
        return cached
    try:
        result = call_llm_json(
            prompt,
            system_prompt=SYSTEM_PROMPT,
            max_output_tokens=2048,
        )
    except ValueError:
        retry_prompt = prompt + "\nReturn one complete compact JSON object only. The previous response was not valid JSON; omit commentary."
        ensure_prompt_budget(retry_prompt, SYSTEM_PROMPT, 2048 + dispatch_padding(True))
        result = call_llm_json(
            retry_prompt,
            system_prompt=SYSTEM_PROMPT,
            max_retries=1,
            max_output_tokens=2048,
        )
    result["reviewed_context_sha256"] = reviewed_hash
    save_checkpoint(case_id, "judge", result)
    print("[Judge] ✓ Done")
    return result
