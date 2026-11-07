"""
Agent 3: IRDAI Checker
Matches the denial against actual IRDAI regulations, circulars,
Ombudsman precedents, and insurer-specific patterns.
Identifies which regulations the insurer may have violated.
This is what makes the appeal legally grounded — not generic complaints.
"""

from tools.llm_client import call_llm_json, dispatch_padding
from tools.irdai_knowledge import CITATION_REVIEW_STATUS, OFFICIAL_SOURCES
from tools.regulatory_registry import load_registry
from tools.document_context import EVIDENCE_BOUNDARY, context_config, ensure_prompt_budget
from tools.io_utils import save_checkpoint, load_checkpoint
from tools.agent_validation import AgentOutputError, validate_agent_output
import json
import hashlib

SYSTEM_PROMPT = """
You are a careful research assistant for Indian health-insurance appeals.
Use only the supplied policy facts and regulatory knowledge. Do not claim that
an insurer violated a rule unless the case facts support it. Treat every
circular identifier, timeline, and Ombudsman summary as a lead requiring human
verification against an official source. Never invent a regulation number,
case name, date, URL, or legal conclusion. Mark uncertain items as requiring
verification and distinguish policy arguments from confirmed law.
""" + "\n" + EVIDENCE_BOUNDARY


def _apply_citation_review_metadata(result: dict) -> dict:
  """Make uncertainty explicit when an LLM omits source verification fields."""
  result["citation_review_status"] = CITATION_REVIEW_STATUS
  result["official_sources"] = OFFICIAL_SOURCES

  for citation in result.get("applicable_regulations", []):
    # A regulator homepage is not evidence for a specific circular.
    citation["verification_status"] = CITATION_REVIEW_STATUS
    citation["official_source_url"] = ""

  for violation in result.get("potential_insurer_violations", []):
    violation["verification_status"] = CITATION_REVIEW_STATUS

  for point in result.get("key_legal_points_for_appeal", []):
    point["verification_status"] = CITATION_REVIEW_STATUS

  return result


def _apply_valid_denial_guardrail(result: dict, policy_analyst_output: dict) -> dict:
  """Keep a facially valid denial in a review posture, not an advocacy posture."""
  if policy_analyst_output.get("rejection_appears_valid") is not True:
    return result

  result["conflict_metadata"] = {
    "rejection_appears_valid": True,
    "regulatory_posture": "review_and_explanation",
    "uncertainty": "The policy analysis supports the denial; regulatory conclusions require human verification.",
    "escalation_claims": "Do not present as strong assertions without new evidence.",
  }
  for violation in result.get("potential_insurer_violations", []):
    violation["strength"] = "weak"
    violation["assertion_status"] = "review_only"
    violation["verification_status"] = CITATION_REVIEW_STATUS
  for point in result.get("key_legal_points_for_appeal", []):
    point["argument_strength"] = "weak"
    point["assertion_status"] = "review_only"
  pathway = result.setdefault("appeal_pathway", {})
  pathway["recommended_first_step"] = "internal_grievance"
  pathway["posture"] = "request_review_and_explanation"
  pathway["estimated_success_probability"] = "not_estimated"
  pathway["escalation_condition"] = "Escalate only after the insurer's explanation is reviewed or new evidence is found."
  return result


def run(auditor_output: dict, policy_analyst_output: dict, case_id: str) -> dict:
    """
    Check the denial against IRDAI regulations.
    Returns applicable regulations, violations, precedents, and appeal rights.
    """
    registry = load_registry()
    denial_category = auditor_output.get("denial_reason_category", "other")
    insurer_name = auditor_output.get("insurer_name") or ""
    evidence = registry.select(denial_category, auditor_output, context_config()["regulatory_budget"])
    print("\n[IRDAI Checker] Checking pinned official source excerpts...")
    regs_context = evidence.text or "No applicable pinned excerpts were selected; request human source review."
    precedents_context = "No independently verified case-law orders are registered. Do not invent precedents."
    insurer_tips = "No verified insurer-specific pattern evidence is supplied."

    prompt = f"""
CLAIM DENIAL DETAILS:
- Insurer: {insurer_name}
- Treatment: {auditor_output.get('treatment_or_procedure')}
- Denial reason: {auditor_output.get('denial_reason_verbatim')}
- Denial category: {denial_category}
- Clause cited: {auditor_output.get('policy_clause_cited')}

POLICY ANALYSIS FINDINGS:
- Rejection appears valid: {policy_analyst_output.get('rejection_appears_valid')}
- Strongest counter arguments: {policy_analyst_output.get('strongest_counter_arguments')}
- Waiting period violation: {policy_analyst_output.get('waiting_period_violation')}
- Exclusion validly applied: {policy_analyst_output.get('exclusion_validly_applied')}

PINNED OFFICIAL SOURCE EXCERPTS (legal applicability requires human review):
{regs_context}

OFFICIAL SOURCES FOR HUMAN VERIFICATION:
{json.dumps(OFFICIAL_SOURCES, indent=2)}

RELEVANT OMBUDSMAN PRECEDENTS:
{precedents_context}

INSURER-SPECIFIC PATTERNS FOR {insurer_name}:
{insurer_tips}

Use only the pinned excerpts for regulatory facts. Treat effective-date qualifications
and companion-circular notices as constraints. A genuine source is not proof of a
case-specific violation. Cite an exact supplied evidence_id and quoted_text for each
source-linked point; otherwise leave them empty and require review.
Based on the above, identify candidate IRDAI regulations, possible concerns,
relevant Ombudsman precedents, and the best appeal rights pathway.

Return a JSON object:
{{
  "applicable_regulations": [
    {{
      "regulation": "Name/number of supplied regulation or circular",
      "evidence_id": "Exact supplied evidence ID, or empty",
      "quoted_text": "Exact supporting source excerpt, or empty",
      "relevance": "How this regulation applies to this case",
      "favours": "policyholder / insurer / neutral",
      "verification_status": "verified / requires_manual_verification",
      "official_source_url": "Official IRDAI or CIO URL, or empty string"
    }}
  ],
  "potential_insurer_violations": [
    {{
      "violation": "What the insurer may have done wrong",
      "regulation_breached": "Which IRDAI rule was breached",
      "strength": "strong / moderate / weak",
      "verification_status": "verified / requires_manual_verification"
    }}
  ],
  "relevant_precedents": [
    {{
      "case_summary": "What happened in the Ombudsman case",
      "how_it_applies": "Why this precedent helps this case",
      "outcome": "What the Ombudsman ruled"
    }}
  ],
  "claim_settlement_timeline_breached": true/false,
  "timeline_breach_details": "If the insurer took longer than IRDAI mandated timelines, explain",
  "procedural_violations": ["Any procedural violations — e.g. verbal denial without written reasoning"],
  "moratorium_applicable": true/false,
  "moratorium_details": "Whether a supplied source supports a moratorium argument; applicability requires review",
  "appeal_pathway": {{
    "recommended_first_step": "internal_grievance / bima_bharosa / ombudsman",
    "reasoning": "Why this step is recommended",
    "ombudsman_eligible": true/false,
    "ombudsman_eligibility_reason": "Why eligible or not",
    "estimated_success_probability": "high / moderate / low",
    "success_reasoning": "Why you estimate this probability"
  }},
  "key_legal_points_for_appeal": [
    {{
      "point": "Candidate legal argument requiring human review",
      "evidence_id": "Exact supplied evidence ID, or empty",
      "quoted_text": "Exact supporting source excerpt, or empty",
      "irdai_citation": "Specific IRDAI rule or circular to cite",
      "precedent_support": "Ombudsman precedent that supports this, if any",
      "argument_strength": "strong / moderate / weak"
    }}
  ],
  "what_documents_to_attach": [
    "List of documents to attach with the appeal letter"
  ],
  "escalation_address": {{
    "internal_grievance": "Write to: Grievance Officer, [Insurer Name] — use insurer's official grievance email",
    "bima_bharosa": "bimabharosa.irdai.gov.in — free online portal",
    "ombudsman": "cioins.co.in — Insurance Ombudsman complaint portal"
  }}
}}
"""

    context_hash = hashlib.sha256(json.dumps(
        [SYSTEM_PROMPT, prompt, auditor_output, policy_analyst_output,
         registry.fingerprint, evidence.as_dict(), context_config()],
        sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    ensure_prompt_budget(prompt, SYSTEM_PROMPT, 1536 + dispatch_padding(True))
    cached = load_checkpoint(case_id, "irdai_checker")
    if cached and cached.get("input_context_sha256") == context_hash:
        return _apply_valid_denial_guardrail(cached, policy_analyst_output)

    result = None
    last_error = None
    for correction_attempt in range(3):
        try:
            request_prompt = prompt
            output_budget = 1536
            if correction_attempt:
                request_prompt = (
                    "Using the case context below, return only a minimal valid JSON "
                    "object. Use empty arrays unless an item is directly supported. "
                    "Each list may contain at most one object; keep every string under "
                    "20 words. Do not invent citations, IDs, URLs, or precedents. "
                    "Do not return a list at the top level or strings inside object lists. "
                    f"Previous validation error: {last_error}\n\n{prompt}"
                )
                output_budget = 1024
            ensure_prompt_budget(request_prompt, SYSTEM_PROMPT, output_budget + dispatch_padding(True))
            raw_result = call_llm_json(
                request_prompt,
                system_prompt=SYSTEM_PROMPT,
                max_output_tokens=output_budget,
            )
            result = validate_agent_output("IRDAI Checker", raw_result)
            break
        except (AgentOutputError, ValueError) as error:
            last_error = error
            if correction_attempt == 2:
                raise
    if result is None:
        raise AgentOutputError(f"IRDAI Checker returned no validated result: {last_error}")
    result = _apply_citation_review_metadata(result)
    result = registry.annotate(result, evidence)
    result["verified_source_context"] = evidence.text
    result["input_context_sha256"] = context_hash
    result = _apply_valid_denial_guardrail(result, policy_analyst_output)
    save_checkpoint(case_id, "irdai_checker", result)
    print("[IRDAI Checker] ✓ Done")
    return result
