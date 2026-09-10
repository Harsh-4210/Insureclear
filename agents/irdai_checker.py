"""
Agent 3: IRDAI Checker
Matches the denial against actual IRDAI regulations, circulars,
Ombudsman precedents, and insurer-specific patterns.
Identifies which regulations the insurer may have violated.
This is what makes the appeal legally grounded — not generic complaints.
"""

from tools.llm_client import call_llm_json
from tools.irdai_knowledge import (
    IRDAI_REGULATIONS,
    OMBUDSMAN_PRECEDENTS,
    INSURER_PATTERNS,
    find_applicable_regulations,
)
from tools.io_utils import save_checkpoint, load_checkpoint
import json

SYSTEM_PROMPT = """
You are an expert in IRDAI (Insurance Regulatory and Development Authority of India) regulations.
You know the Health Insurance Regulations 2016, all subsequent circulars,
Ombudsman rules, precedent cases, and policyholder protection guidelines.
You identify exactly which IRDAI rules an insurer has violated when rejecting a claim.
You also know insurer-specific rejection patterns and how Ombudsman has ruled in similar cases.
"""


def run(auditor_output: dict, policy_analyst_output: dict, case_id: str) -> dict:
    """
    Check the denial against IRDAI regulations.
    Returns applicable regulations, violations, precedents, and appeal rights.
    """
    cached = load_checkpoint(case_id, "irdai_checker")
    if cached:
        return cached

    print("\n[IRDAI Checker] Checking against Indian insurance regulations...")

    # Programmatically find applicable regulations
    denial_category = auditor_output.get("denial_reason_category", "other")
    insurer_name = auditor_output.get("insurer_name", "")
    applicable = find_applicable_regulations(denial_category, insurer_name)

    # Build comprehensive context
    regs_context = json.dumps(IRDAI_REGULATIONS, indent=2)
    precedents_context = json.dumps(applicable.get("precedents", []), indent=2)
    insurer_tips = json.dumps(applicable.get("insurer_tips"), indent=2) if applicable.get("insurer_tips") else "None"

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

IRDAI REGULATORY KNOWLEDGE BASE:
{regs_context}

RELEVANT OMBUDSMAN PRECEDENTS:
{precedents_context}

INSURER-SPECIFIC PATTERNS FOR {insurer_name}:
{insurer_tips}

Based on ALL of the above, identify all applicable IRDAI regulations, violations, 
relevant Ombudsman precedents, and the best appeal rights pathway.

Return a JSON object:
{{
  "applicable_regulations": [
    {{
      "regulation": "Name/number of regulation or circular",
      "relevance": "How this regulation applies to this case",
      "favours": "policyholder / insurer / neutral"
    }}
  ],
  "potential_insurer_violations": [
    {{
      "violation": "What the insurer may have done wrong",
      "regulation_breached": "Which IRDAI rule was breached",
      "strength": "strong / moderate / weak"
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
  "moratorium_details": "If the 8-year moratorium applies, explain how",
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
      "point": "Legal argument to make in the appeal",
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

    result = call_llm_json(prompt, system_prompt=SYSTEM_PROMPT)
    save_checkpoint(case_id, "irdai_checker", result)
    print("[IRDAI Checker] ✓ Done")
    return result
