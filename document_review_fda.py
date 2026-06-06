import json
import re
import time
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from prompt import build_fda_audit_prompt


FDA_GUIDANCE_INDEX_DIR = Path("data/fda_ai/guidance/faiss_index")
FDA_DEVICE_CLEANED_DIR = Path("data/fda_ai/devices/cleaned")
FDA_DEVICE_AUDITED_DIR = Path("data/fda_ai/devices/audited")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_REQUEST_INTERVAL_SECONDS = 1.0
GROQ_TRANSIENT_RETRY_BUFFER_SECONDS = 0.25
GROQ_MAX_TRANSIENT_RETRY_WAIT_SECONDS = 5.0
DEVICE_CHUNK_SIZE = 1800
DEVICE_CHUNK_OVERLAP = 300
DEVICE_PRIMARY_EVIDENCE_CHUNKS = 6
DEVICE_MAX_EVIDENCE_CHUNKS = 10
DEVICE_KEYWORD_WEIGHT = 0.35
PCCP_DIMENSION_PREFIX = "PCCP:"
PCCP_DISCLOSURE_PATTERNS = [
    r"\bpredetermined\s+change\s+control\s+plan\b",
    r"\bPCCP\b",
]

DEVICE_QUERY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "when",
    "with",
}

FDA_AUDIT_DIMENSIONS = {
    "GMLP: Data Collection and Management": {
        "query": (
            "data quality assurance data management representative intended patient population "
            "training test independence reference datasets authenticity integrity cybersecurity"
        ),
        "guidance": "Good Machine Learning Practice (GMLP) Guiding Principles (October 2021)",
        "source_prefixes": ["fda_gmlp_guiding_principles_"],
        "principles": [
            "Principle 2: Good software engineering and security practices are implemented, including data quality assurance, data management, authenticity, integrity, and cybersecurity.",
            "Principle 3: Clinical study participants and datasets are representative of the intended patient population.",
            "Principle 4: Training datasets are independent of test datasets.",
            "Principle 5: Selected reference datasets are based upon best available methods.",
        ],
    },
    "GMLP: Model Development and Validation": {
        "query": (
            "model design intended use overfitting performance degradation human AI team "
            "clinically relevant testing acceptance criteria subgroups confounding factors"
        ),
        "guidance": "Good Machine Learning Practice (GMLP) Guiding Principles (October 2021)",
        "source_prefixes": ["fda_gmlp_guiding_principles_"],
        "principles": [
            "Principle 6: Model design is tailored to the available data and reflects the intended use of the device.",
            "Principle 7: Focus is placed on the performance of the Human-AI team.",
            "Principle 8: Testing demonstrates device performance during clinically relevant conditions.",
        ],
    },
    "GMLP: Deployment and Monitoring": {
        "query": (
            "users clear essential information model performance subgroups training testing data "
            "limitations updates real world performance deployed monitoring retraining dataset drift"
        ),
        "guidance": "Good Machine Learning Practice (GMLP) Guiding Principles (October 2021)",
        "source_prefixes": ["fda_gmlp_guiding_principles_"],
        "principles": [
            "Principle 1: Multi-disciplinary expertise is leveraged throughout the total product lifecycle.",
            "Principle 9: Users are provided clear, essential information.",
            "Principle 10: Deployed models are monitored for performance and retraining risks are managed.",
        ],
    },
    "Transparency: Intended Use and Relevant Information": {
        "query": (
            "transparency MLMD intended use target population workflow inputs outputs performance "
            "benefits risks training testing data clinical studies lifecycle limitations bias"
        ),
        "guidance": "Transparency for Machine Learning-Enabled Medical Devices: Guiding Principles (June 2024)",
        "source_prefixes": ["fda_transparency-ml-devices-guiding-principles_"],
        "principles": [
            "Clearly describe the device medical purpose, function, intended users, use environments, and target populations.",
            "Explain how the device fits into the healthcare workflow, including intended inputs, outputs, and impact on decisions.",
            "Provide relevant information on performance, benefits, risks, development, and lifecycle risk management.",
            "Communicate clinically relevant limitations, known biases, failure modes, and data characterization gaps.",
        ],
    },
    "Transparency: Communication and Human-Centered Design": {
        "query": (
            "transparency relevant audiences placement timing communication user interface "
            "human-centered design logic explainability updates warnings workflow"
        ),
        "guidance": "Transparency for Machine Learning-Enabled Medical Devices: Guiding Principles (June 2024)",
        "source_prefixes": ["fda_transparency-ml-devices-guiding-principles_"],
        "principles": [
            "Provide information appropriate to relevant audiences, including users and those receiving care with the device.",
            "Communicate model logic or explainability information when available and understandable.",
            "Place information where it supports users, including interfaces, labeling, training, alerts, or other modalities.",
            "Provide timely communication for updates, modifications, and workflow-specific warnings.",
            "Apply human-centered design principles to transparency.",
        ],
    },
    "PCCP: Plan Content and Change Control": {
        "query": (
            "predetermined change control plan description of modifications modification protocol "
            "impact assessment traceability planned AI-DSF changes marketing submission"
        ),
        "guidance": "FDA PCCP Final Guidance (updated August 18, 2025; originally issued December 4, 2024)",
        "source_prefixes": ["fda_ai_pccp_final_guidance_2024_"],
        "principles": [
            "If the manufacturer proposes a PCCP, identify the PCCP in the marketing submission.",
            "Describe the specific planned AI-enabled device software function modifications.",
            "Provide a Modification Protocol describing how modifications will be developed, validated, and implemented.",
            "Provide an Impact Assessment covering benefits, risks, and mitigations for the planned modifications.",
            "Maintain traceability between the Description of Modifications and Modification Protocol.",
        ],
    },
    "PCCP: Monitoring, Retraining, and Updates": {
        "query": (
            "PCCP modification protocol data management retraining performance evaluation "
            "update procedures monitoring labeling communication users drift"
        ),
        "guidance": "FDA PCCP Final Guidance (updated August 18, 2025; originally issued December 4, 2024)",
        "source_prefixes": ["fda_ai_pccp_final_guidance_2024_"],
        "principles": [
            "When applicable to a proposed PCCP, describe data management practices.",
            "When applicable to a proposed PCCP, describe retraining practices.",
            "When applicable to a proposed PCCP, describe performance evaluation methods and acceptance criteria.",
            "When applicable to a proposed PCCP, describe update procedures and user communications.",
        ],
    },
    "AI/ML Action Plan: Safety, Transparency, and Lifecycle Oversight": {
        "query": (
            "AI ML SaMD action plan safety effectiveness good machine learning practice "
            "transparency users bias real world performance monitoring lifecycle regulatory science"
        ),
        "guidance": "FDA AI/ML-Based Software as a Medical Device Action Plan (January 2021)",
        "source_prefixes": ["fda_ai_ml_action_plan_2021_"],
        "principles": [
            "Advance Good Machine Learning Practice.",
            "Support a patient-centered approach incorporating transparency to users.",
            "Support methods for evaluating and improving machine learning algorithms, including bias considerations.",
            "Support real-world performance monitoring and a total product lifecycle approach.",
        ],
    },
}

_embedder = None
_index = None
_metadata = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(MODEL_NAME)
    return _embedder


def get_index():
    global _index
    if _index is None:
        _index = faiss.read_index(str(FDA_GUIDANCE_INDEX_DIR / "index.faiss"))
    return _index


def get_metadata():
    global _metadata
    if _metadata is None:
        with open(FDA_GUIDANCE_INDEX_DIR / "metadata.json", "r", encoding="utf-8") as f:
            _metadata = json.load(f)
    return _metadata


def list_device_submissions():
    return sorted(path.name for path in FDA_DEVICE_CLEANED_DIR.glob("*.txt"))


def load_device_submission(filename):
    path = FDA_DEVICE_CLEANED_DIR / filename
    return path.read_text(encoding="utf-8")


def chunk_device_submission(
    device_text,
    max_chars=DEVICE_CHUNK_SIZE,
    overlap_chars=DEVICE_CHUNK_OVERLAP,
):
    text = " ".join(device_text.split())
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split_at = text.rfind(" ", start + (max_chars // 2), end)
            if split_at > start:
                end = split_at

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                {
                    "id": len(chunks) + 1,
                    "start": start,
                    "end": end,
                    "text": chunk_text,
                }
            )

        if end >= len(text):
            break

        next_start = max(0, end - overlap_chars)
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def build_device_evidence_index(device_text):
    chunks = chunk_device_submission(device_text)
    if not chunks:
        raise ValueError("The device submission does not contain readable text.")

    embeddings = get_embedder().encode(
        [chunk["text"] for chunk in chunks],
        normalize_embeddings=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return chunks, index


def get_device_evidence_context(query, principles, chunks, index):
    evidence_queries = [query, *principles]
    query_vectors = get_embedder().encode(
        evidence_queries,
        normalize_embeddings=True,
    ).astype("float32")

    scores, indices = index.search(query_vectors, len(chunks))
    semantic_scores = {}

    for score_row, index_row in zip(scores, indices):
        for score, index_value in zip(score_row, index_row):
            if index_value < 0:
                continue
            semantic_scores[index_value] = max(
                semantic_scores.get(index_value, float("-inf")),
                float(score),
            )

    query_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", " ".join(evidence_queries).lower())
        if len(term) > 2 and term not in DEVICE_QUERY_STOP_WORDS
    }
    keyword_scores = {
        index_value: sum(
            min(chunk["text"].lower().count(term), 3)
            for term in query_terms
        )
        for index_value, chunk in enumerate(chunks)
    }
    max_keyword_score = max(keyword_scores.values(), default=1) or 1
    combined_scores = {
        index_value: semantic_scores.get(index_value, 0.0)
        + DEVICE_KEYWORD_WEIGHT * (keyword_scores[index_value] / max_keyword_score)
        for index_value in range(len(chunks))
    }

    primary_indices = sorted(
        combined_scores,
        key=combined_scores.get,
        reverse=True,
    )[:DEVICE_PRIMARY_EVIDENCE_CHUNKS]
    selected_indices = set(primary_indices)

    neighbor_indices = {
        neighbor
        for index_value in primary_indices
        for neighbor in (index_value - 1, index_value + 1)
        if 0 <= neighbor < len(chunks)
    }
    for neighbor in sorted(
        neighbor_indices - selected_indices,
        key=combined_scores.get,
        reverse=True,
    ):
        if len(selected_indices) >= DEVICE_MAX_EVIDENCE_CHUNKS:
            break
        selected_indices.add(neighbor)

    selected_chunks = sorted(
        (chunks[index_value] for index_value in selected_indices),
        key=lambda chunk: chunk["start"],
    )

    context = "\n\n".join(
        (
            f"[Device Evidence Chunk {chunk['id']}; "
            f"characters {chunk['start']}-{chunk['end']}]\n{chunk['text']}"
        )
        for chunk in selected_chunks
    )
    sources = [
        {
            "chunk": chunk["id"],
            "start": chunk["start"],
            "end": chunk["end"],
        }
        for chunk in selected_chunks
    ]
    return context, sources


def get_guidance_context(query, source_prefixes, k=5):
    metadata = get_metadata()
    index = get_index()
    query_vec = get_embedder().encode(
        [query],
        normalize_embeddings=True,
    ).astype("float32")

    _, indices = index.search(query_vec, index.ntotal)

    matching_items = []
    for i in indices[0]:
        if i < 0:
            continue
        item = metadata[str(i)]
        if any(item["source"].startswith(prefix) for prefix in source_prefixes):
            matching_items.append(item)
        if len(matching_items) >= k:
            break

    if not matching_items:
        raise RuntimeError(f"No guidance chunks matched source prefixes: {source_prefixes}")

    context = "\n\n".join(item["text"][:700] for item in matching_items)
    sources = sorted({item["source"] for item in matching_items})
    return context, sources


def has_disclosed_pccp(device_text):
    return any(
        re.search(pattern, device_text, flags=re.IGNORECASE)
        for pattern in PCCP_DISCLOSURE_PATTERNS
    )


def build_not_applicable_pccp_result(dimension, principles):
    principle_assessments = "\n".join(
        (
            f"- Principle: {principle}\n"
            "  Feature Scope: PCCP (not disclosed in the reviewed public submission)\n"
            "  Status: NOT APPLICABLE\n"
            "  Submission Evidence: No PCCP is disclosed in the reviewed public submission.\n"
            "  Analysis: This recommendation is conditional on a manufacturer proposing a PCCP."
        )
        for principle in principles
    )

    return f"""Audit Summary:
No PCCP is disclosed in the reviewed public submission. Because {dimension} applies conditionally when a manufacturer proposes a PCCP, this dimension is marked NOT APPLICABLE for this review. This local determination does not establish whether FDA has authorized a PCCP in another public record.

Principle-by-Principle Assessment:
{principle_assessments}

Guidance-Alignment Gaps:
None identified for this conditional PCCP dimension because no PCCP is disclosed in the reviewed public submission.

Insufficient Public Disclosure:
No PCCP is disclosed in the reviewed public submission. If another FDA public record indicates that a PCCP was authorized, reassess this dimension using that record and the relevant PCCP documentation.

Potential Regulatory Concerns:
None identified from the reviewed public submission.

Potential Violations:
None identified from the reviewed public submission.

Risk Level:
NOT APPLICABLE

Recommendations:
Verify the FDA public record for PCCP authorization before treating this conditional dimension as applicable."""


def is_rate_limit_error(error):
    status_code = getattr(error, "status_code", None)
    error_text = str(error).lower()
    return (
        status_code == 429
        or "rate_limit" in error_text
        or "rate limit" in error_text
        or "tokens per day" in error_text
    )


def get_rate_limit_scope(error):
    if not is_rate_limit_error(error):
        return None

    error_text = str(error).lower()
    if "tokens per day" in error_text or "(tpd)" in error_text:
        return "daily"
    if "tokens per minute" in error_text or "(tpm)" in error_text:
        return "minute"
    return "unknown"


def get_rate_limit_retry_delay(error):
    error_text = str(error).lower()
    milliseconds = re.search(r"try again in\s+([\d.]+)\s*ms", error_text)
    if milliseconds:
        delay = float(milliseconds.group(1)) / 1000
    else:
        seconds = re.search(r"try again in\s+([\d.]+)\s*s", error_text)
        delay = float(seconds.group(1)) if seconds else 1.0

    return delay + GROQ_TRANSIENT_RETRY_BUFFER_SECONDS


def is_brief_per_minute_rate_limit(error):
    return (
        get_rate_limit_scope(error) == "minute"
        and get_rate_limit_retry_delay(error) <= GROQ_MAX_TRANSIENT_RETRY_WAIT_SECONDS
    )


def should_block_remaining_audits(error):
    return get_rate_limit_scope(error) in {"daily", "unknown"}


def wait_for_groq_pacing(last_request_at):
    if last_request_at is None:
        return

    elapsed = time.monotonic() - last_request_at
    delay = GROQ_REQUEST_INTERVAL_SECONDS - elapsed
    if delay > 0:
        time.sleep(delay)


def request_groq_audit(client, prompt, last_request_at=None):
    wait_for_groq_pacing(last_request_at)

    for attempt in range(2):
        request_at = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an FDA regulatory compliance expert specializing in "
                            "AI-enabled medical devices. Distinguish nonbinding guidance "
                            "recommendations from legally enforceable requirements."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            return response, request_at, None
        except Exception as error:
            if attempt == 0 and is_brief_per_minute_rate_limit(error):
                time.sleep(get_rate_limit_retry_delay(error))
                continue
            return None, request_at, error

    raise RuntimeError("Groq audit request retry loop ended unexpectedly.")


def summarize_audit_run(audits):
    status_counts = {
        "completed": 0,
        "error": 0,
        "skipped": 0,
    }
    for result in audits.values():
        status = result.get("status", "completed")
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_dimensions": len(audits),
        "completed_dimensions": status_counts["completed"],
        "failed_dimensions": status_counts["error"],
        "skipped_dimensions": status_counts["skipped"],
        "has_errors": status_counts["error"] > 0 or status_counts["skipped"] > 0,
        "all_failed": status_counts["completed"] == 0,
    }


def audit_device_submission(device_text, client, k=5, progress_callback=None):
    audits = {}
    device_chunks, device_index = build_device_evidence_index(device_text)
    blocking_error = None
    last_groq_request_at = None
    pccp_disclosed = has_disclosed_pccp(device_text)
    total_dimensions = len(FDA_AUDIT_DIMENSIONS)

    for dimension_index, (dimension, config) in enumerate(FDA_AUDIT_DIMENSIONS.items(), start=1):
        if progress_callback:
            progress_callback(
                {
                    "current_dimension": dimension,
                    "current_dimension_index": dimension_index,
                    "total_dimensions": total_dimensions,
                    "completed_dimensions": max(0, dimension_index - 1),
                    "message": f"Auditing {dimension}",
                }
            )

        if dimension.startswith(PCCP_DIMENSION_PREFIX) and not pccp_disclosed:
            audits[dimension] = {
                "status": "completed",
                "determination": "not_applicable",
                "audit": build_not_applicable_pccp_result(
                    dimension=dimension,
                    principles=config["principles"],
                ),
                "error": "",
                "sources": [],
                "guidance": config["guidance"],
                "principles": config["principles"],
                "device_evidence": [],
            }
            if progress_callback:
                progress_callback(
                    {
                        "current_dimension": dimension,
                        "current_dimension_index": dimension_index,
                        "total_dimensions": total_dimensions,
                        "completed_dimensions": dimension_index,
                        "message": f"Completed {dimension}",
                    }
                )
            continue

        if blocking_error:
            audits[dimension] = {
                "status": "skipped",
                "audit": "",
                "error": blocking_error,
                "sources": [],
                "guidance": config["guidance"],
                "principles": config["principles"],
                "device_evidence": [],
            }
            if progress_callback:
                progress_callback(
                    {
                        "current_dimension": dimension,
                        "current_dimension_index": dimension_index,
                        "total_dimensions": total_dimensions,
                        "completed_dimensions": dimension_index,
                        "message": f"Skipped {dimension}",
                    }
                )
            continue

        try:
            context, sources = get_guidance_context(
                config["query"],
                source_prefixes=config["source_prefixes"],
                k=k,
            )
            device_evidence, device_evidence_sources = get_device_evidence_context(
                query=config["query"],
                principles=config["principles"],
                chunks=device_chunks,
                index=device_index,
            )
            prompt = build_fda_audit_prompt(
                guidance_context=context,
                device_evidence=device_evidence,
                dimension_name=dimension,
                guidance_name=config["guidance"],
                principles=config["principles"],
            )
            response, last_groq_request_at, request_error = request_groq_audit(
                client=client,
                prompt=prompt,
                last_request_at=last_groq_request_at,
            )
            if request_error:
                raise request_error
            audit_text = response.choices[0].message.content.strip()
            if not audit_text:
                raise RuntimeError("The audit model returned an empty response.")
            status = "completed"
            error_message = ""
        except Exception as e:
            audit_text = ""
            status = "error"
            error_message = str(e)
            sources = []
            device_evidence_sources = []
            if should_block_remaining_audits(e):
                blocking_error = (
                    "Skipped because Groq rate limiting prevented completion of the previous "
                    f"audit dimension. Original error: {error_message}"
                )

        audits[dimension] = {
            "status": status,
            "audit": audit_text,
            "error": error_message,
            "sources": sources,
            "guidance": config["guidance"],
            "principles": config["principles"],
            "device_evidence": device_evidence_sources,
        }

        if progress_callback:
            progress_callback(
                {
                    "current_dimension": dimension,
                    "current_dimension_index": dimension_index,
                    "total_dimensions": total_dimensions,
                    "completed_dimensions": dimension_index,
                    "message": f"Completed {dimension}",
                }
            )

    return {
        "audits": audits,
        "summary": summarize_audit_run(audits),
    }


def audit_device_file(filename, client, k=5, progress_callback=None):
    device_text = load_device_submission(filename)
    return audit_device_submission(
        device_text,
        client,
        k=k,
        progress_callback=progress_callback,
    )


def parse_audit_result(result_text):
    sections = {
        "audit_summary": "",
        "principle_assessment": "",
        "guidance_alignment_gaps": "",
        "insufficient_public_disclosure": "",
        "potential_regulatory_concerns": "",
        "potential_violations": "",
        "risk_level": "",
        "recommendations": "",
    }

    mappings = {
        "Audit Summary:": "audit_summary",
        "Principle-by-Principle Assessment:": "principle_assessment",
        "Guidance-Alignment Gaps:": "guidance_alignment_gaps",
        "Insufficient Public Disclosure:": "insufficient_public_disclosure",
        "Potential Regulatory Concerns:": "potential_regulatory_concerns",
        "Potential Violations:": "potential_violations",
        "Risk Level:": "risk_level",
        "Recommendations:": "recommendations",
    }

    current_key = None
    for line in result_text.split("\n"):
        line = line.strip()
        matched = False
        for label, key in mappings.items():
            if line.startswith(label):
                current_key = key
                sections[key] = line[len(label):].strip()
                matched = True
                break
        if not matched and current_key and line and line != "---":
            sections[current_key] = "\n".join(
                part for part in [sections[current_key], line] if part
            )

    risk = sections["risk_level"].strip().lstrip("-").strip()
    sections["risk_level"] = risk or "UNKNOWN"

    return sections


def save_audit_result(device_filename, results):
    FDA_DEVICE_AUDITED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = FDA_DEVICE_AUDITED_DIR / f"{Path(device_filename).stem}_audit.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return output_path


# Backward-compatible aliases.
review_fda_device = audit_device_submission
review_fda_device_file = audit_device_file
parse_fda_review_result = parse_audit_result
save_fda_audit_result = save_audit_result
