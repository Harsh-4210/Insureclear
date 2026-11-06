"""
InsureClear — Streamlit Web Interface
Upload denial + policy PDFs → get an AI-generated appeal letter.
"""

import sys
import json
import time
import streamlit as st
from pathlib import Path
from io import StringIO

# Project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.main import run_pipeline
from tools.io_utils import clear_session
from tools.llm_client import get_stats


MIN_APPROVE_SCORE = 0.75


SAMPLE_DENIAL_FILE = PROJECT_ROOT / "data" / "samples" / "sample_denial.txt"
SAMPLE_POLICY_FILE = PROJECT_ROOT / "data" / "samples" / "sample_policy.txt"

# ── Page Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="InsureClear — Indian Health Insurance Appeal Generator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .main-header {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 2.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(48, 43, 99, 0.3);
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2.4rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: rgba(255, 255, 255, 0.75);
        font-size: 1.05rem;
        margin: 0.5rem 0 0 0;
        font-weight: 300;
    }

    .stat-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        transition: transform 0.2s ease;
    }
    .stat-card:hover { transform: translateY(-2px); }
    .stat-card .value {
        color: #7f5af0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .stat-card .label {
        color: rgba(255, 255, 255, 0.6);
        font-size: 0.85rem;
        margin-top: 0.3rem;
    }

    .agent-badge {
        display: inline-block;
        padding: 0.35rem 0.85rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .badge-running {
        background: rgba(255, 193, 7, 0.15);
        color: #ffc107;
        border: 1px solid rgba(255, 193, 7, 0.3);
    }
    .badge-done {
        background: rgba(76, 175, 80, 0.15);
        color: #4caf50;
        border: 1px solid rgba(76, 175, 80, 0.3);
    }
    .badge-error {
        background: rgba(244, 67, 54, 0.15);
        color: #f44336;
        border: 1px solid rgba(244, 67, 54, 0.3);
    }

    .score-display {
        font-size: 3rem;
        font-weight: 700;
        text-align: center;
        padding: 1rem;
    }
    .score-high { color: #4caf50; }
    .score-medium { color: #ff9800; }
    .score-low { color: #f44336; }

    .appeal-output {
        background: #0d1117;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 2rem;
        font-family: 'Inter', monospace;
        font-size: 0.9rem;
        line-height: 1.8;
        white-space: pre-wrap;
        color: #e6edf3;
    }

    .next-steps {
        background: linear-gradient(135deg, #1b4332, #2d6a4f);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid rgba(76, 175, 80, 0.3);
    }
    .next-steps h4 { color: #95d5b2; margin: 0 0 0.75rem 0; }
    .next-steps li { color: rgba(255, 255, 255, 0.85); margin: 0.5rem 0; }

    .stButton > button {
        background: linear-gradient(135deg, #7f5af0, #6c3ddb) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.65rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(127, 90, 240, 0.3) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #6c3ddb, #5a2dc5) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(127, 90, 240, 0.4) !important;
    }

    .upload-area {
        border: 2px dashed rgba(127, 90, 240, 0.3);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        transition: border-color 0.3s ease;
    }
    .upload-area:hover { border-color: rgba(127, 90, 240, 0.6); }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29, #1a1a2e);
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🛡️ InsureClear</h1>
    <p>Indian Health Insurance Appeal Generator — Powered by IRDAI Regulations</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    input_mode = st.radio(
        "Input Mode",
        ["📄 Upload PDFs", "📝 Paste Text", "🎯 Demo Mode"],
        index=2,
        help="Choose how to provide your documents"
    )

    case_id = st.text_input(
        "Case ID (optional)",
        placeholder="auto-generated if empty",
        help="Name your case for checkpoint/resume"
    )

    fresh_run = st.checkbox("🔄 Fresh run (ignore checkpoints)", value=False)

    st.markdown("---")
    st.markdown("### 📚 How It Works")
    st.markdown("""
    1. **Auditor** — Parses your documents
    2. **Policy Analyst** — Finds hidden traps
    3. **IRDAI Checker** — Matches against regulations
    4. **Appeal Writer** — Drafts your letter
    5. **Judge** — Scores & validates quality
    """)

    st.markdown("---")
    st.markdown("### 🔗 Useful Links")
    st.markdown("[IRDAI Bima Bharosa](https://bimabharosa.irdai.gov.in)")
    st.markdown("[Insurance Ombudsman](https://cioins.co.in)")
    st.markdown("[IRDAI Official](https://www.irdai.gov.in)")


# ── Input Section ────────────────────────────────────────────────
denial_text = None
policy_text = None
denial_pdf = "web_upload"
policy_pdf = "web_upload"


def _read_text_file(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8").strip()
        return content or None
    except Exception:
        return None


def _load_sample_documents() -> tuple[str | None, str | None, list[str]]:
    warnings = []
    denial = _read_text_file(SAMPLE_DENIAL_FILE)
    policy = _read_text_file(SAMPLE_POLICY_FILE)

    if denial is None:
        warnings.append(f"Missing or unreadable sample denial file: {SAMPLE_DENIAL_FILE.name}")
    if policy is None:
        warnings.append(f"Missing or unreadable sample policy file: {SAMPLE_POLICY_FILE.name}")

    return denial, policy, warnings

if input_mode == "🎯 Demo Mode":
    st.info("🎯 **Demo Mode** — Using built-in sample denial letter and policy document. Click 'Generate Appeal' to see the full pipeline in action.")

    denial_text, policy_text, demo_warnings = _load_sample_documents()
    for warning in demo_warnings:
        st.warning(warning)

    if denial_text and policy_text:
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("📄 Sample Denial Letter", expanded=False):
                st.text(denial_text[:500] + "...")
        with col2:
            with st.expander("📋 Sample Policy Document", expanded=False):
                st.text(policy_text[:500] + "...")
    else:
        st.error("Demo data is not available. Upload PDFs or paste text to continue.")

elif input_mode == "📄 Upload PDFs":
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="upload-area">', unsafe_allow_html=True)
        denial_file = st.file_uploader("📄 Upload Denial/Rejection Letter", type=["pdf"], key="denial_pdf")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="upload-area">', unsafe_allow_html=True)
        policy_file = st.file_uploader("📋 Upload Policy Document", type=["pdf"], key="policy_pdf")
        st.markdown('</div>', unsafe_allow_html=True)

    if denial_file and policy_file:
        # Save uploaded files temporarily
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        denial_path = temp_dir / "denial.pdf"
        policy_path = temp_dir / "policy.pdf"
        denial_path.write_bytes(denial_file.read())
        policy_path.write_bytes(policy_file.read())
        denial_pdf = str(denial_path)
        policy_pdf = str(policy_path)

elif input_mode == "📝 Paste Text":
    col1, col2 = st.columns(2)
    with col1:
        denial_text = st.text_area(
            "📄 Paste Denial Letter Text",
            height=300,
            placeholder="Paste the full text of your claim rejection letter here..."
        )
    with col2:
        policy_text = st.text_area(
            "📋 Paste Policy Document Text",
            height=300,
            placeholder="Paste the relevant sections of your policy document here..."
        )

# ── Generate Button ──────────────────────────────────────────────
st.markdown("")
generate_col1, generate_col2, generate_col3 = st.columns([1, 2, 1])
with generate_col2:
    generate = st.button("🚀 Generate Appeal Letter", use_container_width=True)

if generate:
    import uuid

    if input_mode == "🎯 Demo Mode" and (not denial_text or not policy_text):
        st.error("Demo mode requires both sample documents to be present.")
        st.stop()

    # Validate inputs
    if input_mode == "📄 Upload PDFs" and (not denial_file or not policy_file):
        st.error("Please upload both denial letter and policy document PDFs.")
        st.stop()
    elif input_mode == "📝 Paste Text" and (not denial_text or not policy_text):
        st.error("Please paste both the denial letter and policy document text.")
        st.stop()
    elif input_mode == "🎯 Demo Mode" and (not denial_text or not policy_text):
        st.error("Demo mode requires both sample documents to be present.")
        st.stop()

    if denial_text is not None and len(denial_text.split()) < 10:
        st.error("Denial letter text is too short. Please check the input document.")
        st.stop()
    if policy_text is not None and len(policy_text.split()) < 10:
        st.error("Policy document text is too short. Please check the input document.")
        st.stop()

    # Set case ID
    cid = case_id if case_id else f"web_{uuid.uuid4().hex[:8]}"

    # ── Pipeline Execution ────────────────────────────────────────
    progress = st.progress(0, text="Starting pipeline...")

    try:
        if fresh_run:
            clear_session(cid)

        def update_progress(event):
            progress.progress(event.get("percent") or 0, text=event.get("message") or "Processing...")

        full_report = run_pipeline(
            denial_pdf=denial_pdf,
            policy_pdf=policy_pdf,
            case_id=cid,
            denial_text=denial_text,
            policy_text=policy_text,
            progress_callback=update_progress,
        )
        auditor_result = full_report["auditor"]
        policy_result = full_report["policy_analyst"]
        irdai_result = full_report["irdai_checker"]
        judge_result = full_report["judge"]
        letter = full_report["appeal_letter"]
        score = full_report["pipeline_stats"]["final_score"]
        recommendation = full_report["pipeline_stats"]["final_recommendation"]
        revision_count = full_report["pipeline_stats"]["revision_count"]
        output_dir = Path(full_report["artifacts"]["output_dir"])
        progress.progress(100, text="Draft processing complete")
        if recommendation == "VALIDATION_ERROR":
            st.error("This draft failed evidence validation. Review the report before using it.")
        for reason in full_report.get("review_reasons", []):
            st.warning(reason)

        # ── Results Display ───────────────────────────────────────
        st.markdown("---")
        st.markdown("## 📊 Pipeline Results")

        # Stats row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            score_class = "score-high" if score >= 0.75 else ("score-medium" if score >= 0.5 else "score-low")
            st.markdown(f"""<div class="stat-card">
                <div class="value {score_class}">{score:.0%}</div>
                <div class="label">Quality Score</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="stat-card">
                <div class="value" style="color: {'#4caf50' if recommendation == 'APPROVE' else '#ff9800'}">{recommendation}</div>
                <div class="label">Recommendation</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            pathway = irdai_result.get("appeal_pathway", {})
            prob = pathway.get("estimated_success_probability", "N/A")
            prob_color = "#4caf50" if prob == "high" else ("#ff9800" if prob == "moderate" else "#f44336")
            st.markdown(f"""<div class="stat-card">
                <div class="value" style="color: {prob_color}">{prob.upper() if isinstance(prob, str) else prob}</div>
                <div class="label">Success Probability</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            violations = irdai_result.get("potential_insurer_violations", [])
            st.markdown(f"""<div class="stat-card">
                <div class="value" style="color: #ff5252">{len(violations)}</div>
                <div class="label">Violations Found</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("")

        # Tabs for detailed results
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "✉️ Appeal Letter",
            "🔍 Case Analysis",
            "⚖️ IRDAI Findings",
            "👨‍⚖️ Quality Review",
            "📋 Full Report"
        ])

        with tab1:
            st.markdown("### Your Appeal Letter")
            st.markdown(f'<div class="appeal-output">{letter}</div>', unsafe_allow_html=True)

            st.markdown("")
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "📥 Download Appeal Letter (.txt)",
                    letter,
                    file_name=f"appeal_letter_{cid}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with col_dl2:
                st.download_button(
                    "📥 Download Full Report (.json)",
                    json.dumps(full_report, indent=2, ensure_ascii=False),
                    file_name=f"full_report_{cid}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # Next steps guide
            st.markdown("")
            st.markdown("""<div class="next-steps">
                <h4>📌 What To Do Next</h4>
                <ol>
                    <li><strong>Fill in placeholders</strong> — Replace [POLICYHOLDER NAME], [DATE], [INSURER ADDRESS] with your details</li>
                    <li><strong>Attach documents</strong> — Hospital bills, discharge summary, doctor's certificate, policy copy</li>
                    <li><strong>Review before sending</strong> — Verify every case fact, source reference and proposed argument with a reviewer.</li>
                    <li><strong>Check applicable timelines</strong> — Use the response and escalation periods established by the sources applicable to your case.</li>
                    <li><strong>If no response</strong> — Escalate to <a href="https://bimabharosa.irdai.gov.in" target="_blank">Bima Bharosa</a> (free)</li>
                    <li><strong>If still unresolved</strong> — File with <a href="https://cioins.co.in" target="_blank">Insurance Ombudsman</a> (check current eligibility and applicable limits)</li>
                </ol>
            </div>""", unsafe_allow_html=True)

        with tab2:
            st.markdown("### Case Analysis")

            # Auditor findings
            st.markdown("#### 📄 Extracted Information")
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.markdown(f"**Insurer:** {auditor_result.get('insurer_name', 'N/A')}")
                st.markdown(f"**Policy No:** {auditor_result.get('policy_number', 'N/A')}")
                st.markdown(f"**Claim No:** {auditor_result.get('claim_number', 'N/A')}")
                st.markdown(f"**Treatment:** {auditor_result.get('treatment_or_procedure', 'N/A')}")
                st.markdown(f"**Hospital:** {auditor_result.get('hospital_name', 'N/A')}")
            with info_col2:
                st.markdown(f"**Claim Amount:** {auditor_result.get('claim_amount', 'N/A')}")
                st.markdown(f"**Sum Insured:** {auditor_result.get('sum_insured', 'N/A')}")
                st.markdown(f"**Denial Date:** {auditor_result.get('denial_date', 'N/A')}")
                st.markdown(f"**Denial Type:** {auditor_result.get('denial_reason_category', 'N/A')}")
                st.markdown(f"**TPA:** {auditor_result.get('tpa_name', 'N/A')}")

            st.markdown(f"**Denial Reason (verbatim):** {auditor_result.get('denial_reason_verbatim', 'N/A')}")

            # Policy Analyst findings
            st.markdown("---")
            st.markdown("#### 📋 Policy Analysis")
            valid = policy_result.get("rejection_appears_valid")
            if valid:
                st.warning(f"⚠️ Rejection appears valid: {policy_result.get('rejection_validity_explanation', '')}")
            else:
                st.success(f"✅ Rejection appears challengeable: {policy_result.get('rejection_validity_explanation', '')}")

            counter_args = policy_result.get("strongest_counter_arguments", [])
            if counter_args:
                st.markdown("**Strongest Counter-Arguments:**")
                for arg in counter_args:
                    st.markdown(f"- {arg}")

        with tab3:
            st.markdown("### IRDAI Regulatory Findings")

            # Violations
            violations = irdai_result.get("potential_insurer_violations", [])
            if violations:
                st.markdown("#### 🚨 Potential Insurer Violations")
                for v in violations:
                    strength = v.get("strength", "moderate")
                    icon = "🔴" if strength == "strong" else ("🟡" if strength == "moderate" else "⚪")
                    st.markdown(f"{icon} **{v.get('violation', '')}**")
                    st.markdown(f"   Regulation: {v.get('regulation_breached', 'N/A')} | Strength: {strength}")

            # Legal points
            legal_points = irdai_result.get("key_legal_points_for_appeal", [])
            if legal_points:
                st.markdown("#### ⚖️ Key Legal Points for Appeal")
                for lp in legal_points:
                    st.markdown(f"- **{lp.get('point', '')}**")
                    st.markdown(f"  Citation: {lp.get('irdai_citation', 'N/A')}")

            # Appeal pathway
            pathway = irdai_result.get("appeal_pathway", {})
            if pathway:
                st.markdown("#### 🛤️ Recommended Appeal Pathway")
                st.markdown(f"**First step:** {pathway.get('recommended_first_step', 'N/A')}")
                st.markdown(f"**Reasoning:** {pathway.get('reasoning', 'N/A')}")
                st.markdown(f"**Ombudsman eligible:** {'Yes ✅' if pathway.get('ombudsman_eligible') else 'No ❌'}")
                st.markdown(f"**Success probability:** {pathway.get('estimated_success_probability', 'N/A')}")

        with tab4:
            st.markdown("### Quality Review (Judge Agent)")

            # Score breakdown
            dimensions = {
                "factual_accuracy": "Factual Accuracy",
                "irdai_citation_quality": "IRDAI Citation Quality",
                "argument_strength": "Argument Strength",
                "structure_integrity": "Structure & Format",
            }

            for key, label in dimensions.items():
                score_val = judge_result.get(key, 0)
                notes = judge_result.get(f"{key}_notes", "")
                st.markdown(f"**{label}:** {score_val:.0%}")
                st.progress(float(score_val) if isinstance(score_val, (int, float)) else 0.0)
                if notes:
                    st.caption(notes)

            # Hallucination flags
            hallucinations = judge_result.get("hallucination_flags", [])
            if hallucinations and hallucinations != ["List any claims in the letter that are NOT supported by the source documents"]:
                st.markdown("#### ⚠️ Hallucination Flags")
                for h in hallucinations:
                    st.warning(h)

            # Missing elements
            missing = judge_result.get("missing_elements", [])
            if missing and missing != ["List important arguments or citations that should be added but are absent"]:
                st.markdown("#### 📝 Missing Elements")
                for m in missing:
                    st.info(m)

        with tab5:
            st.markdown("### Full Report (JSON)")
            st.json(full_report)

    except EnvironmentError as e:
        st.error(f"❌ Configuration error: {e}")
        st.markdown("**Fix:** Create a `.env` file in the project root with `GEMINI_API_KEY=your_key_here`")
    except Exception as e:
        st.error(f"❌ Pipeline error: {e}")
        st.exception(e)
    finally:
        if input_mode == "📄 Upload PDFs" and "temp_dir" in locals():
            for filename in ("denial.pdf", "policy.pdf"):
                (temp_dir / filename).unlink(missing_ok=True)
            try:
                temp_dir.rmdir()
            except OSError:
                pass

# ── Footer ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: rgba(255,255,255,0.4); font-size: 0.85rem;">
    InsureClear — Built for Indian policyholders 🇮🇳 | Not legal advice — consult a lawyer for complex cases
    <br>
    <a href="https://bimabharosa.irdai.gov.in" target="_blank" style="color: rgba(127, 90, 240, 0.7);">Bima Bharosa</a> •
    <a href="https://cioins.co.in" target="_blank" style="color: rgba(127, 90, 240, 0.7);">Insurance Ombudsman</a> •
    <a href="https://www.irdai.gov.in" target="_blank" style="color: rgba(127, 90, 240, 0.7);">IRDAI</a>
</div>
""", unsafe_allow_html=True)
