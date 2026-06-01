import json
import os
import textwrap
from pathlib import Path

import faiss
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

from prompt import build_prompt
from fpdf import FPDF
from document_reader import extract_document_text
from document_review import review_document, parse_review_result
from document_review_fda import (
    audit_device_submission,
    audit_device_file,
    list_device_submissions,
    parse_audit_result,
    save_audit_result,
)

load_dotenv()

# ---------- LOAD SYSTEM ----------
api_key = os.getenv("GROQ_API_KEY", "").strip().strip("()\"'").strip()
if not api_key:
    st.error("GROQ_API_KEY is missing. Add it to your .env file.")
    st.stop()

client = Groq(api_key=api_key)

embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")

index = faiss.read_index("data/privacy/faiss_index/index.faiss")

with open("data/privacy/faiss_index/metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)


# ---------- RISK SCORING ----------
def get_risk_score(answer):
    answer_lower = answer.lower()

    # Check non-compliant first because it also contains "compliant".
    if "not compliant" in answer_lower:
        return 25, "HIGH"
    if "partially compliant" in answer_lower:
        return 60, "MEDIUM"
    if "compliant" in answer_lower:
        return 90, "LOW"
    return 50, "UNKNOWN"


def parse_answer(answer):
    sections = {
        "final_answer": "",
        "explanation": "",
        "compliance_status": "",
        "recommendations": "",
    }

    mappings = {
        "Final Answer:": "final_answer",
        "Explanation:": "explanation",
        "Compliance Status:": "compliance_status",
        "Recommendations:": "recommendations",
    }

    current_key = None
    for line in answer.split("\n"):
        line = line.strip()
        matched = False
        for label, key in mappings.items():
            if line.startswith(label):
                current_key = key
                sections[key] = line[len(label) :].strip()
                matched = True
                break
        if not matched and current_key and line:
            sections[current_key] += " " + line

    return sections

def export_pdf(question, parsed, score, risk):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "AI Compliance Report", ln=True)
    pdf.ln(5)

    for label, value in [
        ("Question", question),
        ("Final Answer", parsed["final_answer"]),
        ("Explanation", parsed["explanation"]),
        ("Compliance Status", parsed["compliance_status"]),
        ("Recommendations", parsed["recommendations"]),
        ("Risk Score", f"{score}%"),
        ("Risk Level", risk)
    ]:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"{label}:", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 7, value)
        pdf.ln(2)

    return bytes(pdf.output())


def export_review_pdf(filename, results, parse_review_result):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "AI Compliance Review Report", ln=True)

    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, f"Document: {filename}", ln=True)
    pdf.ln(5)

    for regulation, result_text in results.items():
        parsed = parse_review_result(result_text)
        risk = parsed["risk_level"].strip().upper()

        # Regulation header
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_fill_color(40, 40, 40)
        pdf.cell(0, 10, f"{regulation} Review  |  Risk: {risk}", ln=True)
        pdf.ln(3)

        for label, key in [
            ("Compliance Summary", "compliance_summary"),
            ("Compliant Sections", "compliant_sections"),
            ("Violations Found", "violations"),
            ("Missing Requirements", "missing_requirements"),
            ("Recommendations", "recommendations")
        ]:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"{label}:", ln=True)
            pdf.set_font("Helvetica", size=10)
            # Clean the text for PDF
            clean_text = parsed[key].strip().encode(
                "latin-1", errors="replace"
            ).decode("latin-1")
            pdf.multi_cell(0, 6, clean_text)
            pdf.ln(3)

        pdf.ln(5)
        pdf.set_draw_color(100, 100, 100)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    return bytes(pdf.output())


def clean_pdf_text(value, width=90):
    text = str(value or "").encode("latin-1", errors="replace").decode("latin-1")
    wrapped_lines = []
    for line in text.splitlines() or [""]:
        if not line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(
            textwrap.wrap(
                line,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )
    return "\n".join(wrapped_lines)


def write_pdf_block(pdf, value, line_height=6, width=90):
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, line_height, clean_pdf_text(value, width=width))
    pdf.set_x(pdf.l_margin)


def get_fda_audits(results):
    return results.get("audits", results)


def get_fda_audit_status(result):
    if not isinstance(result, dict):
        return "completed"
    if result.get("status"):
        return result["status"]
    if result.get("audit", "").startswith("Error auditing"):
        return "error"
    return "completed"


def get_fda_audit_error(result):
    if not isinstance(result, dict):
        return ""
    return result.get("error") or (
        result.get("audit", "") if get_fda_audit_status(result) == "error" else ""
    )


def get_completed_fda_audits(results):
    return {
        dimension: result
        for dimension, result in get_fda_audits(results).items()
        if get_fda_audit_status(result) == "completed"
    }


def get_fda_audit_summary(results):
    summary = results.get("summary") if isinstance(results, dict) else None
    if summary:
        return summary

    audits = get_fda_audits(results)
    statuses = [get_fda_audit_status(result) for result in audits.values()]
    completed = statuses.count("completed")
    errors = statuses.count("error")
    skipped = statuses.count("skipped")
    return {
        "total_dimensions": len(statuses),
        "completed_dimensions": completed,
        "failed_dimensions": errors,
        "skipped_dimensions": skipped,
        "has_errors": errors > 0 or skipped > 0,
        "all_failed": completed == 0,
    }


def export_audit_pdf(filename, results):
    completed_audits = get_completed_fda_audits(results)
    if not completed_audits:
        raise ValueError("Cannot export an FDA audit PDF without completed findings.")

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "FDA AI Device Audit Report", ln=True)

    pdf.set_font("Helvetica", size=10)
    write_pdf_block(pdf, f"Submission: {filename}", line_height=8, width=80)
    pdf.ln(5)

    for dimension, result in completed_audits.items():
        audit_text = result["audit"] if isinstance(result, dict) else result
        sources = result.get("sources", []) if isinstance(result, dict) else []
        guidance = result.get("guidance", "") if isinstance(result, dict) else ""
        parsed = parse_audit_result(audit_text)
        risk = parsed["risk_level"].strip().upper()

        pdf.set_font("Helvetica", "B", 14)
        write_pdf_block(pdf, f"{dimension}  |  Risk: {risk}", line_height=10, width=70)
        if guidance:
            pdf.set_font("Helvetica", size=10)
            write_pdf_block(pdf, f"Named Guidance: {guidance}")
        pdf.ln(3)

        for label, key in [
            ("Audit Summary", "audit_summary"),
            ("Principle-by-Principle Assessment", "principle_assessment"),
            ("Guidance-Alignment Gaps", "guidance_alignment_gaps"),
            ("Insufficient Public Disclosure", "insufficient_public_disclosure"),
            ("Potential Regulatory Concerns", "potential_regulatory_concerns"),
            ("Potential Violations", "potential_violations"),
            ("Recommendations", "recommendations"),
        ]:
            clean = parsed[key].strip().encode("latin-1", errors="replace").decode("latin-1")
            clean = clean if clean else "N/A"
            value = clean_pdf_text(clean)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"{label}:", ln=True)
            pdf.set_font("Helvetica", size=10)
            write_pdf_block(pdf, value)
            pdf.ln(3)

        if sources:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, "Guidance Sources Used:", ln=True)
            pdf.set_font("Helvetica", size=10)
            for source in sources:
                clean_source = source.encode("latin-1", errors="replace").decode("latin-1")
                if len(clean_source) > 80:
                    clean_source = clean_source[:77] + "..."
                write_pdf_block(pdf, f"- {clean_source}")
            pdf.ln(3)

        pdf.set_draw_color(100, 100, 100)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    return bytes(pdf.output())


# ---------- MAIN FUNCTION ----------
def ask(question, k=5):
    query_vec = embedder.encode([question], normalize_embeddings=True).astype("float32")

    _, indices = index.search(query_vec, k)

    context = "\n\n".join(metadata[str(i)]["text"][:400] for i in indices[0])
    prompt = build_prompt(context, question)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a legal compliance assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return f"API Error: {str(e)}", 50, "UNKNOWN", []

    score, risk = get_risk_score(answer)

    log = {
        "question": question,
        "retrieved_chunks": [metadata[str(i)]["source"] for i in indices[0]],
        "answer": answer,
        "risk_score": score,
        "risk_level": risk,
    }

    with open("logs.json", "a", encoding="utf-8") as f:
        json.dump(log, f)
        f.write("\n")

    sources = sorted({metadata[str(i)]["source"] for i in indices[0]})
    return answer, score, risk, sources


# ---------- UI ----------
st.set_page_config(page_title="AI Compliance Advisor", layout="wide")

st.title("AI Compliance Advisor")
st.markdown("Analyze regulatory compliance using AI (CCPA, HIPAA, HITECH)")

mode = st.radio(
    "Choose Mode:",
    ["Ask a Question", "Review a Document", "FDA AI Device Audit"],
    horizontal=True
)

if "history" not in st.session_state:
    st.session_state.history = []


# -------- Q&A MODE --------

if mode == "Ask a Question":
    user_input = st.text_area(
        "Enter your question or company policy:",
        height=150,
        placeholder="Example: A company sells user data without consent. Is this compliant with CCPA?"
    )

    if st.button("Analyze Compliance"):
        if user_input.strip() == "":
            st.warning("Please enter a question or policy.")
        else:
            with st.spinner("Analyzing..."):
                answer, score, risk, sources = ask(user_input)

            if answer.startswith("API Error:"):
                st.error(answer)
            else:
                parsed = parse_answer(answer)
                st.session_state.history.append({
                    "question": user_input,
                    "answer": parsed["final_answer"],
                    "score": score,
                    "risk": risk,
                    "sources": sources,
                })

                st.subheader("📋 AI Analysis")
                st.markdown("**Final Answer:**")
                st.write(parsed["final_answer"])
                st.markdown("**Explanation:**")
                st.write(parsed["explanation"])
                st.markdown("**Compliance Status:**")
                st.write(parsed["compliance_status"])
                st.markdown("**Recommendations:**")
                st.write(parsed["recommendations"])

                if "not applicable" not in parsed["compliance_status"].lower():
                    st.subheader("📊 Risk Assessment")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Risk Score", f"{score}%")
                    with col2:
                        st.metric("Risk Level", risk)
                    if risk == "HIGH":
                        st.error("⚠️ High compliance risk detected")
                    elif risk == "MEDIUM":
                        st.warning("⚠️ Medium compliance risk")
                    elif risk == "LOW":
                        st.success("✅ Low compliance risk")

                with st.expander("📚 Sources Used"):
                    for s in sources:
                        st.write(f"- {s}")

                pdf_bytes = export_pdf(user_input, parsed, score, risk)
                st.download_button(
                    label="📄 Export as PDF",
                    data=pdf_bytes,
                    file_name="compliance_report.pdf",
                    mime="application/pdf"
                )

# -------- DOCUMENT REVIEW MODE --------

elif mode == "Review a Document":
    uploaded_file = st.file_uploader(
        "Upload your company document",
        type=["pdf", "docx", "txt"]
    )

    if uploaded_file is not None:
        if st.button("Review Document"):
            with st.spinner("Extracting text from document..."):
                document_text = extract_document_text(uploaded_file)

            if not document_text:
                st.error("Could not read the document. Please try a different file.")
            else:
                st.success(f"✅ Document loaded: {len(document_text.split())} words extracted")

                with st.spinner("Reviewing against CCPA, HIPAA, and HITECH... this may take a moment"):
                    results = review_document(document_text, client)

                st.subheader("📋 Compliance Review Results")

                for regulation, result_text in results.items():
                    parsed_result = parse_review_result(result_text)

                    with st.expander(f"📜 {regulation} Review", expanded=True):
                        risk = parsed_result["risk_level"].strip()

                        if "HIGH" in risk.upper():
                            st.error(f"⚠️ Risk Level: {risk}")
                        elif "MEDIUM" in risk.upper():
                            st.warning(f"⚠️ Risk Level: {risk}")
                        elif "LOW" in risk.upper():
                            st.success(f"✅ Risk Level: {risk}")

                        st.markdown("**Summary:**")
                        st.write(parsed_result["compliance_summary"])

                        st.markdown("**✅ Compliant Sections:**")
                        st.write(parsed_result["compliant_sections"])

                        st.markdown("**❌ Violations Found:**")
                        st.write(parsed_result["violations"])

                        st.markdown("**⚠️ Missing Requirements:**")
                        st.write(parsed_result["missing_requirements"])

                        st.markdown("**🔧 Recommendations:**")
                        st.write(parsed_result["recommendations"])

                # DOWNLOAD BUTTON HERE #
               
                st.divider()
                review_pdf_bytes = export_review_pdf(
                    uploaded_file.name,
                    results,
                    parse_review_result
                )
                st.download_button(
                    label="📄 Download Full Compliance Report",
                    data=review_pdf_bytes,
                    file_name=f"compliance_review_{uploaded_file.name}.pdf",
                    mime="application/pdf"
                )

# -------- FDA AI DEVICE AUDIT MODE --------

elif mode == "FDA AI Device Audit":
    st.markdown(
        "Audit FDA-cleared AI medical device submissions against FDA guidance "
        "on transparency, training data, validation, and post-market monitoring."
    )

    source_mode = st.radio(
        "Submission source:",
        ["Upload a PDF", "Use processed submission"],
        horizontal=True,
    )

    audit_results = None
    audit_filename = None

    if source_mode == "Upload a PDF":
        uploaded_file = st.file_uploader(
            "Upload a 510(k) or FDA device submission PDF",
            type=["pdf"],
        )

        if uploaded_file is not None and st.button("Run FDA Audit"):
            audit_filename = uploaded_file.name

            with st.spinner("Extracting text from submission..."):
                device_text = extract_document_text(uploaded_file)

            if not device_text:
                st.error("Could not read the submission. Please try a different file.")
            else:
                st.success(f"Submission loaded: {len(device_text.split())} words extracted")

                with st.spinner(
                    "Auditing against FDA guidance on all dimensions... this may take a moment"
                ):
                    audit_results = audit_device_submission(device_text, client)
                    saved_path = save_audit_result(audit_filename, audit_results)

                st.info(f"Audit run saved to {saved_path}")

    else:
        device_files = list_device_submissions()

        if not device_files:
            st.warning("No cleaned FDA device submissions found. Run scripts/process_device_submissions.py first.")
        else:
            selected_device = st.selectbox(
                "Select an FDA-cleared device submission",
                device_files,
            )

            if st.button("Run FDA Audit"):
                audit_filename = selected_device

                with st.spinner(
                    "Auditing against FDA guidance on all dimensions... this may take a moment"
                ):
                    audit_results = audit_device_file(selected_device, client)
                    saved_path = save_audit_result(selected_device, audit_results)

                st.info(f"Audit run saved to {saved_path}")

    if audit_results:
        st.subheader("FDA AI Device Audit Results")
        audit_summary = get_fda_audit_summary(audit_results)
        completed_dimensions = audit_summary["completed_dimensions"]
        total_dimensions = audit_summary["total_dimensions"]

        if audit_summary["all_failed"]:
            st.error(
                "The FDA audit could not be completed. No findings report was generated. "
                "The model provider rejected the audit requests. Review the error below and "
                "run the audit again after the issue is resolved."
            )
        elif audit_summary["has_errors"]:
            st.warning(
                f"The audit completed {completed_dimensions} of {total_dimensions} dimensions. "
                "Only completed findings will appear in the PDF report."
            )

        for dimension, result in get_fda_audits(audit_results).items():
            audit_text = result["audit"] if isinstance(result, dict) else result
            sources = result.get("sources", []) if isinstance(result, dict) else []
            guidance = result.get("guidance", "") if isinstance(result, dict) else ""
            status = get_fda_audit_status(result)

            with st.expander(dimension, expanded=True):
                if guidance:
                    st.caption(f"Named Guidance: {guidance}")

                if status != "completed":
                    if status == "skipped":
                        st.warning("This dimension was skipped after an earlier audit failure.")
                    else:
                        st.error("This dimension could not be audited.")
                    error_message = get_fda_audit_error(result)
                    error_message_lower = error_message.lower()
                    if "tokens per minute" in error_message_lower or "(tpm)" in error_message_lower:
                        st.write(
                            "Groq per-minute token limit reached after one automatic retry. "
                            "Wait briefly, then run the audit again."
                        )
                    elif "rate limit" in error_message_lower or "rate_limit" in error_message_lower:
                        st.write(
                            "Groq rate limit reached. Wait for the quota to reset, then run the "
                            "audit again."
                        )
                    with st.expander("Technical Error Details"):
                        st.code(error_message or "No technical error details were returned.")
                    continue

                parsed_result = parse_audit_result(audit_text)
                risk = parsed_result["risk_level"].strip()
                if "HIGH" in risk.upper():
                    st.error(f"Risk Level: {risk}")
                elif "MEDIUM" in risk.upper():
                    st.warning(f"Risk Level: {risk}")
                elif "LOW" in risk.upper():
                    st.success(f"Risk Level: {risk}")
                else:
                    st.info(f"Risk Level: {risk or 'UNKNOWN'}")

                st.markdown("**Audit Summary:**")
                st.write(parsed_result["audit_summary"])

                st.markdown("**Principle-by-Principle Assessment:**")
                st.write(parsed_result["principle_assessment"])

                st.markdown("**Guidance-Alignment Gaps:**")
                st.write(parsed_result["guidance_alignment_gaps"])

                st.markdown("**Insufficient Public Disclosure:**")
                st.write(parsed_result["insufficient_public_disclosure"])

                st.markdown("**Potential Regulatory Concerns:**")
                st.write(parsed_result["potential_regulatory_concerns"])

                st.markdown("**Potential Violations:**")
                st.write(parsed_result["potential_violations"])

                st.markdown("**Recommendations:**")
                st.write(parsed_result["recommendations"])

                if sources:
                    with st.expander("FDA Guidance Sources Used"):
                        for source in sources:
                            st.write(f"- {source}")

        st.divider()
        audit_download_stem = Path(audit_filename).stem
        if completed_dimensions:
            audit_pdf_bytes = export_audit_pdf(audit_filename, audit_results)
            st.download_button(
                label="Download Full Audit Report",
                data=audit_pdf_bytes,
                file_name=f"fda_audit_{audit_download_stem}.pdf",
                mime="application/pdf",
            )
        else:
            st.warning("PDF download is unavailable because no audit findings were generated.")

        st.download_button(
            label="Download FDA Audit JSON",
            data=json.dumps(audit_results, indent=2),
            file_name=f"{audit_download_stem}_audit.json",
            mime="application/json",
        )

# -------- HISTORY (outside both modes) --------                        
if len(st.session_state.history) > 1:
    st.subheader("Previous Questions")
    for item in reversed(st.session_state.history[:-1]):
        with st.expander(item["question"]):
            st.write(item["answer"])
            st.caption(f"Risk Score: {item['score']}%")
            st.caption(f"Risk Level: {item['risk']}")
            with st.expander("Sources Used"):
                for source in item["sources"]:
                    st.write(f"- {source}")
