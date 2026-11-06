"""
Evaluation Cases
Ten synthetic Indian health-insurance denials with a hand-written answer key.
Insurers, people and numbers are fictional. Seven denials are challengeable
and three are valid, so the pipeline is also tested on knowing when NOT to fight.

Each policy is built from one intentionally short template. Long-document
retrieval and context-boundary behavior are covered by separate regression tests.
"""

POLICY_TEMPLATE = """{insurer_upper}
{plan} - POLICY SCHEDULE AND WORDINGS

Policy Number: {policy_number}
Policyholder: {holder}
Policy Period: {period}
First Inception With Us: {inception}
{portability_line}Sum Insured: Rs {sum_insured}

SECTION 1: COVERAGE
1.1 In-patient hospitalisation for a minimum of 24 hours is covered.
1.2 Day Care Procedures: treatments listed in Annexure A (including cataract surgery,
chemotherapy, dialysis and lithotripsy) are covered without the 24-hour requirement.
1.3 Pre-hospitalisation 30 days and post-hospitalisation 60 days are covered.

SECTION 2: LIMITS
2.1 Room rent: up to Rs {room_rent} per day. If a higher room category is chosen, a
proportionate deduction applies to associated medical expenses. Proportionate deduction
shall NOT apply to pharmacy, consumables, implants, medical devices and diagnostics.
2.2 ICU charges: up to Rs {icu_rent} per day.

SECTION 3: WAITING PERIODS
3.1 Initial waiting period: 30 days from first inception, except for claims arising
from an accident.
3.2 Specific diseases (cataract, hernia, joint replacement, kidney stones): 24 months.
3.3 Pre-existing diseases: 36 months of continuous coverage.
3.4 Portability: waiting periods already served under a previous Indian health policy
are credited to the extent of the previous sum insured.

SECTION 4: MORATORIUM
4.1 After completion of 60 continuous months of coverage, no policy or claim shall be
contestable on grounds of non-disclosure or misrepresentation, except for established fraud.

SECTION 5: PERMANENT EXCLUSIONS
5.1 Cosmetic or aesthetic treatment, unless needed for reconstruction after an accident,
burns or cancer.
5.2 Treatment for alcohol or drug abuse.
5.3 Experimental or unproven treatment.

SECTION 6: CLAIMS PROCEDURE
6.1 Intimation within 48 hours of emergency admission. Delay shall be condoned where
the insured shows the delay was for reasons beyond their control.
6.2 Documents required: claim form, discharge summary, final bill, investigation reports.

SECTION 7: GRIEVANCE
7.1 Write to the Grievance Officer, {insurer}. Unresolved complaints may go to
Bima Bharosa or the Insurance Ombudsman.
"""

DENIAL_TEMPLATE = """CLAIM REJECTION LETTER

Date: {denial_date}
Claim No: {claim_number}
Policy No: {policy_number}

To,
{holder}

Dear {salutation},

We refer to your claim for treatment at {hospital} from {admission}. The claim for
{treatment}, amounting to Rs {claim_amount}, has been {outcome}.

Reason:
{reason}

You may contact our Grievance Officer within 30 days of this letter.

Yours sincerely,
Claims Department
{insurer}
"""

_DEFAULTS = {
    "plan": "COMPREHENSIVE FAMILY HEALTH PLAN",
    "period": "1 April 2025 to 31 March 2026",
    "portability_line": "",
    "sum_insured": "5,00,000",
    "room_rent": "5,000",
    "icu_rent": "10,000",
    "outcome": "rejected",
}

CASES = [
    {
        "id": "c01_moratorium",
        "insurer": "Suraksha Health Insurance Co. Ltd.",
        "policy_number": "SHI4410028731",
        "claim_number": "CLM-SHI-2025-55102",
        "holder": "Mr. Anil Deshmukh",
        "salutation": "Mr. Deshmukh",
        "inception": "1 April 2019 (renewed every year without a break)",
        "denial_date": "20 November 2025",
        "hospital": "Sahyadri Hospital, Pune",
        "admission": "2 November 2025 to 7 November 2025",
        "treatment": "management of diabetic foot infection",
        "claim_amount": "2,10,000",
        "reason": "Our investigation found that you were diagnosed with Type 2 Diabetes in 2017 "
                  "and did not disclose it in your 2019 proposal form. The claim is rejected for "
                  "non-disclosure of a material fact and the policy is liable for cancellation.",
        "answer": {
            "denial_category": ["non_disclosure", "pre_existing_condition"],
            "rejection_valid": False,
            "key_argument": "Moratorium: more than 60 continuous months of cover, so non-disclosure cannot be raised",
            "key_terms": ["moratorium", "60 months", "60 continuous months", "five years", "5 years"],
        },
    },
    {
        "id": "c02_portability",
        "insurer": "Nirmal General Insurance Ltd.",
        "policy_number": "NGI7720419935",
        "claim_number": "NGI/HC/2025/31877",
        "holder": "Mrs. Kavita Rao",
        "salutation": "Mrs. Rao",
        "inception": "15 June 2025",
        "portability_line": "Ported from: Arogya Shield Insurance, policy AS-55120, continuous cover "
                            "since 1 June 2021, sum insured Rs 5,00,000\n",
        "period": "15 June 2025 to 14 June 2026",
        "denial_date": "5 December 2025",
        "hospital": "Lotus Eye Hospital, Bengaluru",
        "admission": "28 November 2025 (day care)",
        "treatment": "cataract surgery of the right eye",
        "claim_amount": "48,000",
        "reason": "Cataract is subject to a 24-month specific disease waiting period under "
                  "Clause 3.2. Your policy with us began on 15 June 2025, so the waiting period "
                  "has not been completed.",
        "answer": {
            "denial_category": ["waiting_period"],
            "rejection_valid": False,
            "key_argument": "Portability: over 4 years of earlier cover must be credited to the waiting period",
            "key_terms": ["portab", "ported", "credit"],
        },
    },
    {
        "id": "c03_room_rent",
        "insurer": "Vishwas Health Insurance Ltd.",
        "policy_number": "VHI3309912284",
        "claim_number": "VHI-CL-889201",
        "holder": "Mr. Rohan Mehta",
        "salutation": "Mr. Mehta",
        "inception": "1 January 2022",
        "period": "1 January 2025 to 31 December 2025",
        "denial_date": "18 October 2025",
        "hospital": "Lilavati Hospital, Mumbai",
        "admission": "3 October 2025 to 6 October 2025",
        "treatment": "knee arthroscopy with implant",
        "claim_amount": "3,40,000",
        "outcome": "partly settled for Rs 1,70,000",
        "reason": "You stayed in a room costing Rs 10,000 per day against the eligible Rs 5,000 "
                  "per day. A 50% proportionate deduction has therefore been applied to the "
                  "entire bill, including implants, pharmacy and diagnostics.",
        "answer": {
            "denial_category": ["room_rent_exceeded"],
            "rejection_valid": False,
            "key_argument": "Proportionate deduction cannot be applied to pharmacy, implants and diagnostics",
            "key_terms": ["implant", "pharmacy", "diagnostic", "consumable"],
        },
    },
    {
        "id": "c04_day_care",
        "insurer": "Suraksha Health Insurance Co. Ltd.",
        "policy_number": "SHI4410077510",
        "claim_number": "CLM-SHI-2025-60233",
        "holder": "Mrs. Sunita Iyer",
        "salutation": "Mrs. Iyer",
        "inception": "1 March 2023",
        "period": "1 March 2025 to 28 February 2026",
        "denial_date": "12 September 2025",
        "hospital": "Apollo Hospital, Chennai",
        "admission": "3 September 2025 (discharged the same day)",
        "treatment": "chemotherapy cycle 3 for breast cancer",
        "claim_amount": "95,000",
        "reason": "The policy covers in-patient hospitalisation of at least 24 hours only. "
                  "You were admitted for less than 24 hours, so the claim is not payable.",
        "answer": {
            "denial_category": ["procedure_not_covered", "policy_exclusion", "other"],
            "rejection_valid": False,
            "key_argument": "Chemotherapy is a listed Day Care Procedure, so the 24-hour rule does not apply",
            "key_terms": ["day care", "daycare", "day-care"],
        },
    },
    {
        "id": "c05_accident_waiting",
        "insurer": "Nirmal General Insurance Ltd.",
        "policy_number": "NGI7720455120",
        "claim_number": "NGI/HC/2025/40912",
        "holder": "Mr. Farhan Qureshi",
        "salutation": "Mr. Qureshi",
        "inception": "10 August 2025",
        "period": "10 August 2025 to 9 August 2026",
        "denial_date": "2 September 2025",
        "hospital": "Ruby Hall Clinic, Pune",
        "admission": "22 August 2025 to 26 August 2025",
        "treatment": "surgery for a fractured forearm after a road accident",
        "claim_amount": "1,25,000",
        "reason": "The hospitalisation occurred 12 days after policy inception, within the "
                  "30-day initial waiting period under Clause 3.1.",
        "answer": {
            "denial_category": ["waiting_period"],
            "rejection_valid": False,
            "key_argument": "Accidents are exempt from the 30-day initial waiting period",
            "key_terms": ["accident"],
        },
    },
    {
        "id": "c06_hernia_valid",
        "insurer": "Vishwas Health Insurance Ltd.",
        "policy_number": "VHI3309955017",
        "claim_number": "VHI-CL-902114",
        "holder": "Mr. Deepak Joshi",
        "salutation": "Mr. Joshi",
        "inception": "1 February 2025 (first health policy, not ported)",
        "period": "1 February 2025 to 31 January 2026",
        "denial_date": "15 October 2025",
        "hospital": "Jehangir Hospital, Pune",
        "admission": "6 October 2025 to 8 October 2025",
        "treatment": "laparoscopic inguinal hernia repair",
        "claim_amount": "85,000",
        "reason": "Hernia is subject to a 24-month specific disease waiting period under Clause "
                  "3.2. Your policy began on 1 February 2025, so the waiting period has not been "
                  "completed.",
        "answer": {
            "denial_category": ["waiting_period"],
            "rejection_valid": True,
            "key_argument": None,
            "key_terms": [],
        },
    },
    {
        "id": "c07_cosmetic_valid",
        "insurer": "Suraksha Health Insurance Co. Ltd.",
        "policy_number": "SHI4410090346",
        "claim_number": "CLM-SHI-2025-61980",
        "holder": "Ms. Neha Kapoor",
        "salutation": "Ms. Kapoor",
        "inception": "1 May 2021",
        "period": "1 May 2025 to 30 April 2026",
        "denial_date": "8 August 2025",
        "hospital": "Fortis Hospital, Delhi",
        "admission": "28 July 2025 to 29 July 2025",
        "treatment": "rhinoplasty to change the shape of the nose for aesthetic reasons, "
                     "with no history of injury",
        "claim_amount": "1,60,000",
        "reason": "Cosmetic or aesthetic treatment is permanently excluded under Clause 5.1. "
                  "The discharge summary records the surgery as elective and aesthetic.",
        "answer": {
            "denial_category": ["policy_exclusion", "procedure_not_covered"],
            "rejection_valid": True,
            "key_argument": None,
            "key_terms": [],
        },
    },
    {
        "id": "c08_documents_submitted",
        "insurer": "Nirmal General Insurance Ltd.",
        "policy_number": "NGI7720461893",
        "claim_number": "NGI/HC/2025/42277",
        "holder": "Mr. Suresh Patil",
        "salutation": "Mr. Patil",
        "inception": "1 July 2020",
        "period": "1 July 2025 to 30 June 2026",
        "denial_date": "30 September 2025",
        "hospital": "Deenanath Mangeshkar Hospital, Pune",
        "admission": "1 September 2025 to 5 September 2025",
        "treatment": "treatment for pneumonia",
        "claim_amount": "1,05,000",
        "reason": "The discharge summary was not received despite our reminder dated "
                  "18 September 2025. The claim is closed for want of documents. "
                  "(Our records show your upload on 12 September 2025, acknowledgement "
                  "ACK-77310, contained the claim form, discharge summary, final bill and investigation reports.)",
        "answer": {
            "denial_category": ["documentation_missing"],
            "rejection_valid": False,
            "key_argument": "Documents were already uploaded (ACK-77310); claim should be reopened, not closed",
            "key_terms": ["ACK-77310", "acknowledg", "reopen", "resubmit", "re-submit"],
        },
    },
    {
        "id": "c09_late_intimation",
        "insurer": "Vishwas Health Insurance Ltd.",
        "policy_number": "VHI3309970462",
        "claim_number": "VHI-CL-915630",
        "holder": "Mrs. Lata Kulkarni",
        "salutation": "Mrs. Kulkarni",
        "inception": "1 September 2018",
        "period": "1 September 2025 to 31 August 2026",
        "denial_date": "25 October 2025",
        "hospital": "KEM Hospital, Pune",
        "admission": "4 October 2025 to 14 October 2025",
        "treatment": "emergency treatment for a stroke, including 5 days in the ICU while "
                     "unconscious",
        "claim_amount": "4,20,000",
        "reason": "The claim was intimated on 9 October 2025, five days after emergency "
                  "admission, against the required 48 hours under Clause 6.1. The claim is "
                  "rejected for late intimation.",
        "answer": {
            "denial_category": ["other", "documentation_missing"],
            "rejection_valid": False,
            "key_argument": "Delay was beyond the insured's control (unconscious in ICU), so it must be condoned",
            "key_terms": ["unconscious", "icu", "intensive care", "condon", "beyond"],
        },
    },
    {
        "id": "c10_initial_waiting_valid",
        "insurer": "Suraksha Health Insurance Co. Ltd.",
        "policy_number": "SHI4410101129",
        "claim_number": "CLM-SHI-2025-63305",
        "holder": "Mr. Vikram Singh",
        "salutation": "Mr. Singh",
        "inception": "5 September 2025 (first health policy, not ported)",
        "period": "5 September 2025 to 4 September 2026",
        "denial_date": "30 September 2025",
        "hospital": "Max Hospital, Gurugram",
        "admission": "17 September 2025 to 20 September 2025",
        "treatment": "treatment for dengue fever",
        "claim_amount": "70,000",
        "reason": "The illness began 12 days after policy inception, within the 30-day initial "
                  "waiting period under Clause 3.1. Dengue is not an accident.",
        "answer": {
            "denial_category": ["waiting_period"],
            "rejection_valid": True,
            "key_argument": None,
            "key_terms": [],
        },
    },
]


def build_documents(case: dict) -> tuple[str, str]:
    """Return (denial_text, policy_text) for one case."""
    values = {**_DEFAULTS, **case}
    values["insurer_upper"] = values["insurer"].upper()
    policy = POLICY_TEMPLATE.format(**values)
    denial = DENIAL_TEMPLATE.format(**values)
    return denial, policy
