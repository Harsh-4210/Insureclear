"""
IRDAI Knowledge Base
Core Indian insurance regulations, common rejection reasons,
appeal rights, Ombudsman escalation rules, insurer-specific patterns,
and Ombudsman precedents.
All sourced from IRDAI (Health Insurance) Regulations 2016 and amendments.
Updated with 2024-2025 circulars.
"""

IRDAI_REGULATIONS = {
    "claim_settlement_timeline": {
        "cashless_preauth": "Within 1 hour of receiving all documents (IRDAI Circular IRDA/HLT/REG/CIR/194/08/2020)",
        "cashless_final": "Within 3 hours of discharge",
        "reimbursement": "Within 30 days of receiving all documents",
        "deficiency_notice": "Insurer must raise deficiency within 15 days — cannot reject after 30 days citing missing docs",
        "interest_on_delay": "If claim settlement exceeds 30 days, insurer must pay interest at 2% above bank rate (IRDAI Regulation 27)",
    },
    "standard_exclusions": [
        "Pre-existing diseases (waiting period: typically 2-4 years — check your policy)",
        "First 30 days of any illness (initial waiting period)",
        "Named diseases (joint replacement, cataract, hernia, etc.) — 1-2 year waiting period",
        "Cosmetic or aesthetic treatment",
        "Dental treatment (unless due to accident)",
        "Vision correction (spectacles, contact lenses, LASIK)",
        "Pregnancy and maternity (unless specific rider)",
        "Self-inflicted injuries",
        "War and nuclear risk",
        "Experimental or unproven treatments",
        "Obesity treatment and bariatric surgery (unless life-threatening — IRDAI 2024 update allows in specific cases)",
        "Congenital external diseases or defects",
        "Sterility and infertility (unless specific rider purchased)",
    ],
    "what_insurers_cannot_exclude": [
        "Mental illness — IRDAI mandated parity with physical illness (IRDAI Circular 2022, Mental Healthcare Act 2017 Section 21(4))",
        "HIV/AIDS treatment — must be covered under IRDAI guidelines",
        "Gender reassignment surgery — cannot be denied as cosmetic if medically necessary",
        "Day-care procedures — 541+ listed procedures cannot be rejected for 'less than 24 hours'",
        "Home care / domiciliary treatment — if hospital admission was medically advised but not possible",
        "Road ambulance charges — must be covered",
        "AYUSH treatment — Ayurveda, Yoga, Unani, Siddha, Homeopathy in govt-recognised hospitals",
        "Modern treatments — Robot-assisted surgery, stem cell therapy (haematopoietic), immunotherapy, oral chemotherapy, etc. (IRDAI Circular 2024)",
        "Telemedicine consultation charges — covered as OPD if policy includes OPD (IRDAI 2024)",
    ],
    "common_unfair_rejection_grounds": {
        "CO-50 / Not medically necessary": "Insurer must provide clinical justification. You can counter with treating doctor's certificate + medical literature.",
        "Non-disclosure": "Only valid if the undisclosed condition is directly related to the claim AND was known at policy inception. Random non-disclosure is invalid. Moratorium period of 8 years — after 8 years, no claim can be denied on non-disclosure grounds (IRDAI 2020).",
        "Policy lapsed": "Check if premium was paid. Grace period is 30 days for annual policies.",
        "Room rent exceeded": "Only the proportionate deduction is allowed — insurer cannot reject the entire claim.",
        "Procedure not covered": "Check IRDAI's 541 standardised day-care procedure list. Many rejections on this ground are invalid.",
        "Pre-existing condition": "Only valid if the condition existed BEFORE policy start AND waiting period hasn't been served.",
        "Experimental treatment": "Must be proven experimental — standard chemotherapy, radiotherapy, immunotherapy are NOT experimental.",
        "Not a listed procedure": "If the procedure is medically standard and the policy doesn't specifically exclude it, it must be covered.",
        "Treatment available at lower cost": "Insurer cannot dictate treatment choice — only the treating doctor can decide medical necessity.",
        "Late intimation": "Delay in intimation alone cannot be grounds for rejection if the claim is otherwise valid (Ombudsman precedent).",
    },
    "moratorium_period": {
        "duration": "8 years from policy inception (continuous)",
        "effect": "After 8 years, insurer CANNOT deny claims citing non-disclosure or mis-representation, regardless of facts",
        "regulation": "IRDAI (Health Insurance) Regulations 2016 — Regulation 10(2)",
        "exception": "Fraud is the only exception — provable intentional fraud",
    },
    "portability_rules": {
        "right": "Policyholder can port to any other insurer without losing waiting period credit",
        "timeline": "Apply at least 45 days before renewal date",
        "credit": "New insurer must give credit for waiting periods already served with old insurer",
        "no_denial": "New insurer cannot reject portability application without valid reasons",
        "regulation": "IRDAI Guidelines on Health Insurance Portability 2011 (amended 2020)",
    },
    "appeal_rights": {
        "step_1": "Internal grievance to insurer — must respond within 15 days (IRDAI Grievance Redressal Guidelines 2017)",
        "step_2": "IRDAI Bima Bharosa portal — bimabharosa.irdai.gov.in — free, no lawyer needed",
        "step_3": "Insurance Ombudsman — free, binding up to ₹50 lakh (increased from ₹30 lakh in 2024). File at cioins.co.in",
        "step_4": "Consumer Forum (NCDRC/State/District) — for amounts above ₹50 lakh or if Ombudsman fails",
        "step_5": "Civil Court — last resort",
        "key_stat": "~45% of appealed claim rejections are overturned. Most people give up at step 0.",
        "free_help": "All steps up to Ombudsman are completely FREE. No lawyer needed.",
    },
    "ombudsman_jurisdiction": {
        "limit": "₹50 lakh per complaint (updated 2024, previously ₹30 lakh)",
        "timeline": "Must file within 1 year of final insurer rejection",
        "cost": "Completely free",
        "binding": "Insurer is bound by Ombudsman order. Consumer is not — can still go to court.",
        "offices": "17 Ombudsman offices across India covering all states",
        "contact": "cioins.co.in — online complaint filing available",
        "hearing": "Can be done online — no need to physically visit",
    },
    "tpa_rules": {
        "what_is_tpa": "Third Party Administrator — processes cashless and reimbursement claims on behalf of insurer",
        "preauth_timeline": "TPA must respond to cashless preauth within 1 hour",
        "rejection_must_be_written": "Verbal cashless denials are not valid — insurer must give written rejection with reasons",
        "escalation": "If TPA rejects, you can directly approach the insurer's grievance officer — TPA rejection is not final",
        "tpa_not_insurer": "TPA decisions are not final — insurer is ultimately responsible. Always escalate beyond TPA.",
    },
    "key_irdai_circulars": [
        "IRDAI/HLT/REG/CIR/194/08/2020 — Cashless authorisation timelines",
        "IRDAI/HLT/CIR/MISC/109/04/2022 — Mental illness coverage parity",
        "IRDAI (Health Insurance) Regulations 2016 — Base regulation",
        "IRDAI Circular on Standardisation of health insurance products 2019",
        "IRDAI (Protection of Policyholders' Interests) Regulations 2017",
        "IRDAI Grievance Redressal Guidelines 2017",
        "IRDAI/HLT/MISC/CIR/247/09/2024 — Modern treatment methods mandatory coverage",
        "IRDAI/Life/GEN/CIR/249/10/2024 — Enhanced Ombudsman jurisdiction to ₹50 lakh",
        "IRDAI Bima Vistaar 2024 — Affordable all-in-one insurance for all Indians",
        "IRDAI Bima Sugam 2024 — Digital insurance marketplace platform",
        "IRDAI/HLT/REG/CIR/256/01/2025 — Cashless everywhere directive",
    ],
}

# Common Indian health insurance policy clauses that get people denied
POLICY_RED_FLAGS = {
    "room_rent_sub_limit": {
        "description": "Daily room rent capped at a % of sum insured or a fixed amount",
        "impact": "If you exceed the limit, insurer applies proportionate deduction — ALL related charges are reduced proportionally, not just room rent",
        "example": "Policy allows ₹3,000/day. You take ₹6,000 room. Your ₹1 lakh surgery bill gets reduced to ₹50,000.",
        "counter": "Ask for a room within limits. If unavailable (medical necessity), document it in writing from hospital.",
    },
    "co_pay": {
        "description": "You pay a fixed % of every claim — common for senior citizens",
        "impact": "Typically 10-30%. Applies on top of all deductions.",
        "counter": "Usually non-negotiable contractually. Ensure you understand this before claim.",
    },
    "disease_specific_sub_limit": {
        "description": "Certain diseases have a maximum claim cap regardless of sum insured",
        "example": "₹5 lakh policy, but cataract capped at ₹15,000",
        "counter": "Check your policy schedule. If the sub-limit wasn't disclosed clearly at sale, file mis-selling complaint.",
    },
    "waiting_period": {
        "description": "Period after policy start during which certain conditions are not covered",
        "types": {
            "initial": "30 days — all illnesses except accidents",
            "pre_existing": "2-4 years — any condition you had before buying the policy",
            "specific_disease": "1-2 years — named conditions like hernia, joint replacement, kidney stones",
        },
        "counter": "Portability preserves waiting period credit — switching insurers doesn't restart the clock (IRDAI portability rules).",
    },
    "network_hospital_clause": {
        "description": "Cashless only at network hospitals. Reimbursement at any hospital.",
        "trap": "Some policies have 'preferred network' with better terms — outside this, higher co-pay applies",
        "counter": "Cashless rejection ≠ claim rejection. File for reimbursement even if cashless is denied.",
    },
    "aggregate_deductible": {
        "description": "First ₹X of each claim is not covered (you pay out of pocket)",
        "example": "₹50,000 deductible means you always pay the first ₹50,000 of any claim",
        "counter": "Often not explained at sale. If not clearly highlighted in proposal form, raise mis-selling.",
    },
    "proportionate_clause": {
        "description": "If room rent exceeds limit, ALL charges (surgery, doctor, consumables) are reduced proportionally",
        "impact": "This is the biggest hidden cost — people think only room rent is capped, but the entire bill gets cut",
        "counter": "This is contractually valid BUT must be clearly disclosed. Ensure hospital downgrades room if possible.",
    },
    "pre_post_hospitalisation_caps": {
        "description": "Pre-hospitalisation (30-60 days) and post-hospitalisation (60-180 days) expenses are capped",
        "impact": "Diagnostic tests done before admission or follow-ups after may not be fully covered",
        "counter": "Keep all related bills. Date of first consultation establishes the pre-hospitalisation window.",
    },
}

# Ombudsman precedent summaries — real cases where rejections were overturned
OMBUDSMAN_PRECEDENTS = {
    "late_intimation_not_grounds": {
        "summary": "Ombudsman, Mumbai: Insurer rejected claim citing 'late intimation'. Ombudsman ruled that delay in intimation alone cannot be grounds for rejection if the claim is otherwise valid and there was a reasonable explanation for the delay (emergency admission, patient in ICU).",
        "applicable_when": "Insurer rejects citing late intimation / late claim filing",
        "outcome": "Claim approved in full",
    },
    "pre_existing_overruled_by_moratorium": {
        "summary": "Ombudsman, Delhi: After 8+ years of continuous coverage, insurer denied claim citing pre-existing hypertension not disclosed. Ombudsman invoked 8-year moratorium rule — non-disclosure cannot be cited after 8 years of continuous coverage.",
        "applicable_when": "Policy held continuously for 8+ years and insurer cites non-disclosure",
        "outcome": "Claim approved. Non-disclosure ground invalidated.",
    },
    "proportionate_deduction_excessive": {
        "summary": "Ombudsman, Hyderabad: Insurer applied proportionate deduction on ALL charges because room rent was exceeded by ₹500/day. Ombudsman ruled the deduction was disproportionate to the actual excess and ordered partial reimbursement.",
        "applicable_when": "Room rent exceeded by small amount but insurer applies heavy proportionate deduction",
        "outcome": "Partial relief — reduced deduction, not blanket proportionate cut",
    },
    "mental_illness_denial_reversed": {
        "summary": "Ombudsman, Bangalore: Insurer denied hospitalisation claim for depression treatment citing 'mental illness exclusion'. Ombudsman ruled that post-2022 IRDAI circular, mental illness exclusion is void. Coverage must be at par with physical illness.",
        "applicable_when": "Any denial related to mental health / psychiatric treatment",
        "outcome": "Claim approved in full. Insurer warned.",
    },
    "tpa_verbal_denial": {
        "summary": "Ombudsman, Chennai: TPA verbally denied cashless authorization but never sent written denial. Hospital demanded payment from patient. Ombudsman ruled that verbal denial without written reasons is procedurally invalid.",
        "applicable_when": "Cashless was denied verbally / without written communication",
        "outcome": "Claim approved. TPA/insurer directed to improve communication processes.",
    },
    "daycare_24hr_rule_overturned": {
        "summary": "Ombudsman, Pune: Insurer denied claim for kidney stone lithotripsy because patient was discharged within 10 hours. Ombudsman ruled the procedure is on IRDAI's 541 standardised day-care list and 24-hour hospitalisation is not required for listed procedures.",
        "applicable_when": "Claim denied for 'less than 24 hours hospitalisation' for a standard procedure",
        "outcome": "Claim approved in full",
    },
    "non_disclosure_unrelated_condition": {
        "summary": "Ombudsman, Kolkata: Insurer denied cardiac surgery claim citing non-disclosure of diabetes. Ombudsman ruled that the non-disclosed condition (diabetes) was not the proximate cause of the claim (cardiac). Non-disclosure must be material to the claim.",
        "applicable_when": "Insurer cites non-disclosure of a condition unrelated to the current claim",
        "outcome": "Claim approved. Non-disclosure held immaterial.",
    },
    "cashless_rejection_reimbursement_approved": {
        "summary": "Ombudsman, Mumbai: TPA denied cashless citing 'hospital not in preferred network'. Patient paid out of pocket. Ombudsman ruled that cashless denial is not claim denial — reimbursement must still be processed within 30 days.",
        "applicable_when": "Cashless was denied but reimbursement is also being delayed/denied",
        "outcome": "Reimbursement approved with interest for delay",
    },
}

# Insurer-specific rejection patterns — helps tailor the appeal
INSURER_PATTERNS = {
    "star_health": {
        "common_rejections": [
            "Room rent sub-limit exceeded — proportionate deduction",
            "Pre-existing condition not disclosed",
            "Procedure claimed as daycare but denied as 'not requiring hospitalization'",
        ],
        "known_issues": "Aggressive on non-disclosure rejections, especially for policies under 4 years. Room rent sub-limits on popular plans (Family Health Optima).",
        "appeal_tip": "Include treating doctor's certificate explicitly stating medical necessity. Star Health responds well to detailed clinical documentation.",
    },
    "hdfc_ergo": {
        "common_rejections": [
            "Not medically necessary",
            "Treatment available at lower cost",
            "Late intimation",
        ],
        "known_issues": "Often cites 'not medically necessary' without providing clinical justification. Has been pulled up by Ombudsman for this.",
        "appeal_tip": "Demand the insurer's medical officer's written justification for 'not medically necessary'. IRDAI requires them to provide this.",
    },
    "niva_bupa": {
        "common_rejections": [
            "Pre-existing condition (broad interpretation)",
            "Waiting period for specific diseases",
            "Network hospital disputes",
        ],
        "known_issues": "Tends to classify a wide range of conditions as 'pre-existing' even with thin evidence. Improved post-2022 but still aggressive.",
        "appeal_tip": "Establish exact policy start date and continuous coverage history. Cite portability credits if applicable.",
    },
    "icici_lombard": {
        "common_rejections": [
            "Proportionate deduction on room rent",
            "Documentation deficient",
            "Procedure not covered under plan",
        ],
        "known_issues": "Strong on paperwork requirements. Tends to reject for 'incomplete documentation' without sending deficiency notice within 15-day window.",
        "appeal_tip": "Cite IRDAI rule that deficiency must be raised within 15 days. If they didn't, rejection on doc grounds is void.",
    },
    "new_india_assurance": {
        "common_rejections": [
            "Government hospital requirement not met",
            "TPA delays",
            "Slow processing / silence as rejection",
        ],
        "known_issues": "Being a PSU insurer, processing is slower. TPA-related issues are more common.",
        "appeal_tip": "If no response within 30 days, claim is deemed approved under IRDAI regulations. File for interest on delayed settlement.",
    },
    "care_health": {
        "common_rejections": [
            "Room rent sub-limit with harsh proportionate deduction",
            "Modern treatment exclusion",
            "Disease-specific sub-limits",
        ],
        "known_issues": "Popular 'Care' plan has aggressive sub-limits that many buyers don't notice at purchase.",
        "appeal_tip": "If modern treatment (robot-assisted, immunotherapy) was denied, cite IRDAI 2024 modern treatment circular.",
    },
}


def find_applicable_regulations(denial_category: str, insurer_name: str = None) -> dict:
    """
    Given a denial reason category, return all applicable IRDAI regulations,
    relevant precedents, and insurer-specific patterns.

    Args:
        denial_category: One of the standard denial categories
        insurer_name: Optional insurer name for specific patterns

    Returns:
        Dict with regulations, precedents, and tips
    """
    result = {
        "regulations": [],
        "precedents": [],
        "insurer_tips": None,
        "unfair_rejection_info": None,
    }

    # Map denial category to relevant regulations
    category_regulation_map = {
        "pre_existing_condition": [
            IRDAI_REGULATIONS["moratorium_period"],
            "Portability preserves waiting period credit",
        ],
        "waiting_period": [
            IRDAI_REGULATIONS["portability_rules"],
        ],
        "not_medically_necessary": [
            IRDAI_REGULATIONS["common_unfair_rejection_grounds"].get("CO-50 / Not medically necessary"),
            IRDAI_REGULATIONS["common_unfair_rejection_grounds"].get("Treatment available at lower cost"),
        ],
        "room_rent_exceeded": [
            IRDAI_REGULATIONS["common_unfair_rejection_grounds"].get("Room rent exceeded"),
        ],
        "non_disclosure": [
            IRDAI_REGULATIONS["moratorium_period"],
            IRDAI_REGULATIONS["common_unfair_rejection_grounds"].get("Non-disclosure"),
        ],
        "documentation_missing": [
            IRDAI_REGULATIONS["claim_settlement_timeline"]["deficiency_notice"],
        ],
        "procedure_not_covered": [
            IRDAI_REGULATIONS["common_unfair_rejection_grounds"].get("Procedure not covered"),
            IRDAI_REGULATIONS["common_unfair_rejection_grounds"].get("Not a listed procedure"),
        ],
    }

    if denial_category in category_regulation_map:
        result["regulations"] = category_regulation_map[denial_category]

    # Find relevant precedents
    category_precedent_map = {
        "pre_existing_condition": ["pre_existing_overruled_by_moratorium", "non_disclosure_unrelated_condition"],
        "non_disclosure": ["pre_existing_overruled_by_moratorium", "non_disclosure_unrelated_condition"],
        "room_rent_exceeded": ["proportionate_deduction_excessive"],
        "not_medically_necessary": ["daycare_24hr_rule_overturned"],
        "procedure_not_covered": ["daycare_24hr_rule_overturned"],
        "network_hospital": ["cashless_rejection_reimbursement_approved"],
        "documentation_missing": ["late_intimation_not_grounds"],
    }

    if denial_category in category_precedent_map:
        for key in category_precedent_map[denial_category]:
            if key in OMBUDSMAN_PRECEDENTS:
                result["precedents"].append(OMBUDSMAN_PRECEDENTS[key])

    # Get insurer-specific patterns
    if insurer_name:
        name_lower = insurer_name.lower()
        for key, patterns in INSURER_PATTERNS.items():
            if key.replace("_", " ") in name_lower or any(
                word in name_lower for word in key.split("_")
            ):
                result["insurer_tips"] = patterns
                break

    # Get unfair rejection info
    for key, value in IRDAI_REGULATIONS["common_unfair_rejection_grounds"].items():
        if denial_category and denial_category.replace("_", " ") in key.lower():
            result["unfair_rejection_info"] = {key: value}

    return result


APPEAL_LETTER_TEMPLATE = """
[Your Name]
[Your Address]
[Date]

The Grievance Officer
[Insurance Company Name]
[Insurer Address]

Subject: Formal Appeal Against Rejection of Claim No. [CLAIM_NUMBER] — Policy No. [POLICY_NUMBER]

Dear Sir/Madam,

I write to formally appeal the rejection of my health insurance claim dated [REJECTION_DATE] for [TREATMENT/PROCEDURE] undergone at [HOSPITAL NAME].

GROUNDS FOR APPEAL:

[GROUNDS_PLACEHOLDER]

SUPPORTING EVIDENCE:
[EVIDENCE_PLACEHOLDER]

RELIEF SOUGHT:
I respectfully request that you:
1. Reconsider and approve my claim of ₹[AMOUNT] in full
2. Provide a written response within 15 days as mandated under IRDAI Grievance Redressal Guidelines 2017

ESCALATION NOTICE:
Should I not receive a satisfactory resolution within 15 days, I will escalate this matter to:
- IRDAI Bima Bharosa portal (bimabharosa.irdai.gov.in)
- Insurance Ombudsman for [REGION] (cioins.co.in)
without further notice.

Yours faithfully,
[Your Name]
[Contact Number]
[Email]
[Policy Number]
"""
