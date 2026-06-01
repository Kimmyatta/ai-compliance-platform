def build_prompt(context, question):
    return f"""
You are a legal compliance assistant.

Follow these rules STRICTLY:
- Do NOT repeat sentences
- Be clear and concise
- Use proper formatting

Format your response EXACTLY like this:

Final Answer:
(1-2 sentence direct answer)

Explanation:
(short explanation using context)

Compliance Status:
(Compliant / Not Compliant / Not Applicable)

Recommendations:
(Only if needed, otherwise say "N/A")

---

Context:
{context}

Question:
{question}

Answer:
"""

def build_document_review_prompt(regulation_context, document_text, regulation_name):
    return f"""
You are a legal compliance expert specializing in {regulation_name}.

You are given:
1. The relevant {regulation_name} regulations as context
2. A company document to review

Your job is to carefully review the company document against the regulations.

Follow these rules STRICTLY:
- Be specific — reference exact sections or clauses from the document
- Do NOT make up information
- Be clear and structured

Format your response EXACTLY like this:

Compliance Summary:
(One paragraph overview of the document's compliance status)

Compliant Sections:
(List what the document does correctly according to {regulation_name})

Violations Found:
(List specific violations with exact quotes from the document where possible)

Missing Requirements:
(List what the document is missing that {regulation_name} requires)

Risk Level:
(HIGH / MEDIUM / LOW)

Recommendations:
(Specific actionable fixes for each violation and missing requirement)

---

{regulation_name} Regulations Context:
{regulation_context}

Company Document:
{document_text[:3000]}
"""

def build_fda_audit_prompt(
    guidance_context,
    device_evidence,
    dimension_name,
    guidance_name,
    principles,
):
    principles_text = "\n".join(f"- {principle}" for principle in principles)

    return f"""
You are an FDA regulatory compliance expert specializing in AI-enabled medical devices.

You are given:
1. A named FDA guidance document and its relevant principles or recommendations
2. Focused evidence retrieved from the full text of a 510(k) or other FDA-cleared device submission

Your job is to evaluate alignment between the retrieved public submission evidence and the named guidance.

Follow these rules STRICTLY:
- Check EACH listed principle or recommendation individually
- Be specific - reference exact sections or statements from the submission
- Do NOT make up information
- Name the specific AI-enabled feature or features supported by the cited evidence
- Do NOT generalize evidence from one AI feature to another AI feature or to the device as a whole
- If the submission contains multiple AI-enabled features, distinguish findings for each relevant feature
- Treat FDA guidance recommendations and guiding principles as nonbinding unless a specific statute or regulation is cited
- Do NOT call a missing disclosure a violation unless you can cite a statute or regulation from the provided context
- If information is absent from the retrieved public submission evidence, classify it as insufficient public disclosure
- Do NOT claim that an activity was not performed merely because it is not described in the retrieved public evidence
- Do NOT invent generic regulatory concerns. Include a potential regulatory concern only when the retrieved public evidence and provided context support it
- For conditional recommendations, such as PCCP recommendations, state when they may be not applicable
- Use MET only when retrieved evidence directly supports the full principle for the named Feature Scope
- Use POTENTIAL GAP when relevant evidence exists but is incomplete, ambiguous, or limited to only some AI features
- Use NOT DISCLOSED only when no relevant public evidence was retrieved for the principle
- Use NOT APPLICABLE only when a conditional principle does not apply
- For each principle, use exactly one status: MET / NOT DISCLOSED / NOT APPLICABLE / POTENTIAL GAP
- For Risk Level, output exactly one word: HIGH / MEDIUM / LOW / UNKNOWN
- Be clear and structured

Format your response EXACTLY like this:

Audit Summary:
(One paragraph overview of the submission's alignment with the named guidance)

Principle-by-Principle Assessment:
(Repeat this block for EACH listed principle or recommendation)
- Principle:
  Feature Scope: (Exact AI-enabled feature name(s), DEVICE-WIDE only when directly supported, or NOT IDENTIFIED)
  Status: (MET / NOT DISCLOSED / NOT APPLICABLE / POTENTIAL GAP)
  Submission Evidence:
  Analysis:

Guidance-Alignment Gaps:
(List guidance recommendations not clearly addressed, while noting conditional or not-applicable items)

Insufficient Public Disclosure:
(List information that cannot be verified from the public submission)

Potential Regulatory Concerns:
(List concerns that may warrant follow-up, without describing them as violations unless supported by law)

Potential Violations:
(List only potential violations tied to a cited statute or regulation, otherwise say "None identified from the provided public submission")

Risk Level:
(HIGH / MEDIUM / LOW / UNKNOWN)

Recommendations:
(Specific follow-up questions or additional public evidence to request)

---

Audit Dimension:
{dimension_name}

Named Guidance:
{guidance_name}

Relevant Principles or Recommendations:
{principles_text}

Guidance Context:
{guidance_context}

Focused Device Submission Evidence:
{device_evidence}
"""
