"""
Agent 1: Auditor
Reads the denial letter and policy document.
Extracts structured information: what was denied, why, and what the policy says.
This is the foundation every other agent builds on.
"""

import hashlib
from tools.document_context import EVIDENCE_BOUNDARY, fit_document_prompt, source_marker, retrieval_fingerprint
from tools.llm_client import call_llm_json, dispatch_padding
from tools.io_utils import save_checkpoint, load_checkpoint

SYSTEM_PROMPT = """
You are an expert Indian health insurance document analyst.
You read denial letters and policy documents issued by Indian insurers
(Star Health, HDFC Ergo, Niva Bupa, ICICI Lombard, New India Assurance, etc.)
and extract precise, structured information.
Be exact. Quote directly from documents. Do not infer what is not written.
""" + "\n" + EVIDENCE_BOUNDARY


def run(denial_text: str, policy_text: str, case_id: str) -> dict:
    """
    Parse denial letter + policy document.
    Returns a structured dict with all extracted fields.
    Checkpoints result — won't re-run if already done.
    """
    print("\n[Auditor] Analysing denial letter and policy document...")

    prompt = f"""
You are given two Indian insurance documents.

=== DENIAL LETTER ===
{source_marker("denial")}

=== POLICY DOCUMENT ===
{source_marker("policy")}

Extract and return a JSON object with these exact fields:

{{
  "insurer_name": "Name of the insurance company",
  "policy_number": "Policy number from the documents",
  "claim_number": "Claim reference number if present",
  "policyholder_name": "Name of the insured person",
  "denial_date": "Date of rejection letter",
  "treatment_or_procedure": "What was the medical treatment/procedure/hospitalisation",
  "hospital_name": "Name of the hospital",
  "claim_amount": "Amount claimed in rupees",
  "denial_reason_verbatim": "Exact rejection reason as written in the denial letter",
  "denial_reason_category": "One of: pre_existing_condition | waiting_period | not_medically_necessary | policy_exclusion | room_rent_exceeded | non_disclosure | documentation_missing | procedure_not_covered | network_hospital | other",
  "policy_clause_cited": "Exact clause or section number cited by the insurer if any",
  "policy_clause_text": "Full text of the cited clause from the policy document if found",
  "sum_insured": "Total sum insured under the policy",
  "room_rent_limit": "Daily room rent limit in the policy if mentioned",
  "co_pay_percent": "Co-payment percentage if applicable",
  "waiting_period_relevant": "Any waiting period clause that is relevant to this case",
  "pre_existing_conditions_listed": "Any pre-existing conditions declared or mentioned",
  "policy_start_date": "When the policy started",
  "tpa_name": "TPA (Third Party Administrator) name if mentioned",
  "additional_notes": "Any other relevant observations from the documents"
}}

If any field is not found in the documents, use null.
"""

    prompt, coverage = fit_document_prompt(
        prompt, SYSTEM_PROMPT, {"denial": denial_text, "policy": policy_text}, denial_text, 4096, transport_reserve=dispatch_padding(True)
    )
    context_hash = hashlib.sha256((SYSTEM_PROMPT + prompt + retrieval_fingerprint()).encode()).hexdigest()
    cached = load_checkpoint(case_id, "auditor")
    if cached and cached.get("input_context_sha256") == context_hash:
        return cached

    result = call_llm_json(prompt, system_prompt=SYSTEM_PROMPT)
    if isinstance(result, dict):
        result["input_coverage"] = coverage
        result["input_context_sha256"] = context_hash
    save_checkpoint(case_id, "auditor", result)
    print("[Auditor] ✓ Done")
    return result
