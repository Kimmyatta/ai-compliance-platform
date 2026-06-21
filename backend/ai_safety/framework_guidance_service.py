import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.ai_safety.evaluation_service import _call_groq, clean_and_parse_json, get_scenario
from backend.ai_safety.models import (
    DEFAULT_MODEL,
    FrameworkGuidedRecommendation,
    FrameworkGuidedReport,
    FrameworkSource,
    IdentifiedRisk,
    Scenario,
)
from backend.app.core.config import get_settings


FRAMEWORK_GUIDANCE_PROMPT = """
You are generating framework-guided governance recommendations for an African healthcare AI deployment.

Use the scenario, detected risks, missed risks, and retrieved framework excerpts below.
Your recommendations should be grounded in the framework excerpts, but do not over-quote them.
Do not pretend the excerpts are country-specific law. Treat them as governance guidance that applies across countries,
then adapt the advice to the scenario country and healthcare context.

SCENARIO:
Title: {title}
Country: {country}
Healthcare context: {healthcare_context}
Description: {scenario_description}

DETECTED RISKS:
{detected_risks}

MISSED RISKS FROM BENCHMARK SCORING:
{missed_risks}

RETRIEVED FRAMEWORK EXCERPTS:
{framework_context}

Return only valid JSON in this exact shape:
{{
  "framework_summary": "2-3 sentences explaining the governance concern using the frameworks and scenario context.",
  "recommendations": [
    {{
      "recommendation": "clear action the deployer should take",
      "rationale": "why this follows from the scenario and framework guidance",
      "priority": "High | Medium | Low",
      "related_risks": ["risk category or risk label"],
      "framework_sources": ["source names used"]
    }}
  ],
  "governance_checklist": [
    "short implementation check the reviewer can verify"
  ],
  "limitations_and_dual_use_considerations": [
    "important limitation or dual-use consideration"
  ]
}}
""".strip()


def _index_dir() -> Path:
    return get_settings().afrisafe_frameworks_index_dir


def _metadata_path() -> Path:
    return _index_dir() / "metadata.json"


def _index_path() -> Path:
    return _index_dir() / "index.faiss"


@lru_cache(maxsize=1)
def _embedder() -> SentenceTransformer:
    return SentenceTransformer("BAAI/bge-small-en-v1.5", local_files_only=True)


@lru_cache(maxsize=1)
def _load_index() -> tuple[Any, dict[str, dict[str, str]]]:
    if not _index_path().exists() or not _metadata_path().exists():
        raise ValueError(
            "AfriSafeBench framework index is missing. Run "
            "`python scripts/build_knowledge_base.py afrisafe_frameworks` first."
        )
    index = faiss.read_index(str(_index_path()))
    with _metadata_path().open("r", encoding="utf-8") as file:
        metadata = json.load(file)
    return index, metadata


def _format_risks(risks: list[IdentifiedRisk]) -> str:
    if not risks:
        return "None provided."
    return "\n".join(
        f"- {risk.risk} ({risk.severity}): {risk.explanation}"
        for risk in risks
    )


def _source_label(source: str) -> str:
    label = source.replace("_chunk", " chunk ")
    label = label.replace(".txt", "")
    return label


def _query_terms(query: str) -> set[str]:
    stopwords = {
        "about",
        "across",
        "after",
        "against",
        "also",
        "and",
        "are",
        "based",
        "been",
        "before",
        "being",
        "between",
        "but",
        "can",
        "could",
        "from",
        "has",
        "have",
        "health",
        "healthcare",
        "into",
        "not",
        "that",
        "the",
        "their",
        "this",
        "with",
        "without",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", query.lower())
        if token not in stopwords
    }


def _keyword_retrieve_framework_context(query: str, k: int) -> list[FrameworkSource]:
    _, metadata = _load_index()
    terms = _query_terms(query)
    scored = []
    for item in metadata.values():
        text = str(item.get("text", ""))
        normalized = text.lower()
        score = sum(1 for term in terms if term in normalized)
        if score:
            scored.append((score, str(item.get("source", "framework excerpt")), text))

    scored.sort(key=lambda item: item[0], reverse=True)
    sources: list[FrameworkSource] = []
    seen = set()
    for _, source, text in scored:
        key = (source, text[:120])
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            FrameworkSource(
                source=_source_label(source),
                excerpt=text.strip()[:900],
            )
        )
        if len(sources) >= k:
            break
    return sources


def retrieve_framework_context(query: str, k: int = 6) -> list[FrameworkSource]:
    index, metadata = _load_index()
    try:
        vector = _embedder().encode(query, normalize_embeddings=True)
        query_vector = np.array([vector], dtype="float32")
        _, indices = index.search(query_vector, k)
    except Exception:
        return _keyword_retrieve_framework_context(query, k)

    sources: list[FrameworkSource] = []
    seen = set()
    for raw_index in indices[0]:
        if raw_index < 0:
            continue
        item = metadata.get(str(raw_index))
        if not item:
            continue
        source = str(item.get("source", "framework excerpt"))
        text = str(item.get("text", "")).strip()
        key = (source, text[:120])
        if not text or key in seen:
            continue
        seen.add(key)
        sources.append(
            FrameworkSource(
                source=_source_label(source),
                excerpt=text[:900],
            )
        )
    return sources


def _framework_context_text(sources: list[FrameworkSource]) -> str:
    if not sources:
        return "No framework excerpts were retrieved."
    return "\n\n".join(
        f"[{index + 1}] {source.source}\n{source.excerpt}"
        for index, source in enumerate(sources)
    )


def _parse_framework_report(
    *,
    payload: dict[str, Any],
    scenario: Scenario,
    model: str,
    sources: list[FrameworkSource],
    raw_response: str,
) -> FrameworkGuidedReport:
    recommendations = [
        FrameworkGuidedRecommendation(
            recommendation=str(item.get("recommendation", "")),
            rationale=str(item.get("rationale", "")),
            priority=str(item.get("priority", "Medium")),
            related_risks=[str(value) for value in item.get("related_risks", [])],
            framework_sources=[str(value) for value in item.get("framework_sources", [])],
        )
        for item in payload.get("recommendations", [])
    ]
    return FrameworkGuidedReport(
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        country=scenario.country,
        model=model,
        framework_summary=str(payload.get("framework_summary", "")),
        recommendations=recommendations,
        governance_checklist=[
            str(item) for item in payload.get("governance_checklist", [])
        ],
        limitations_and_dual_use_considerations=[
            str(item)
            for item in payload.get("limitations_and_dual_use_considerations", [])
        ],
        sources=sources,
        raw_model_response=raw_response,
    )


def generate_framework_guidance_for_scenario(
    *,
    scenario_id: str,
    model: str = DEFAULT_MODEL,
    detected_risks: list[dict[str, Any]] | None = None,
    missed_risks: list[str] | None = None,
    k: int = 6,
) -> dict[str, Any]:
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise ValueError(f"AfriSafeBench scenario not found: {scenario_id}")

    risks = [
        IdentifiedRisk(
            risk=str(item.get("risk", "")),
            explanation=str(item.get("explanation", "")),
            severity=str(item.get("severity", "Medium")),
        )
        for item in detected_risks or []
    ]
    missed = missed_risks or []
    retrieval_query = "\n".join(
        [
            scenario.title,
            scenario.country,
            scenario.healthcare_context,
            scenario.scenario_description,
            " ".join(scenario.expected_risk_categories),
            _format_risks(risks),
            " ".join(missed),
        ]
    )
    sources = retrieve_framework_context(retrieval_query, k=k)
    prompt = FRAMEWORK_GUIDANCE_PROMPT.format(
        title=scenario.title,
        country=scenario.country,
        healthcare_context=scenario.healthcare_context,
        scenario_description=scenario.scenario_description,
        detected_risks=_format_risks(risks),
        missed_risks=", ".join(missed) or "None",
        framework_context=_framework_context_text(sources),
    )
    raw_response = _call_groq(prompt, model=model)
    payload = clean_and_parse_json(raw_response)
    return _parse_framework_report(
        payload=payload,
        scenario=scenario,
        model=model,
        sources=sources,
        raw_response=raw_response,
    ).model_dump()


def _rescored_results_dir() -> Path:
    return get_settings().project_root / "data" / "afrisafebench" / "results" / "rescored"


def _is_rescored_result(payload: dict[str, Any]) -> bool:
    return all(
        key in payload
        for key in [
            "scenario_id",
            "title",
            "model",
            "identified_risks",
            "scoring",
        ]
    )


def list_rescored_reviews() -> list[dict[str, Any]]:
    rescored_dir = _rescored_results_dir()
    if not rescored_dir.exists():
        return []

    reviews = []
    for path in sorted(rescored_dir.glob("afrisafebench_*.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except json.JSONDecodeError:
            continue
        if not _is_rescored_result(payload):
            continue
        scoring = payload.get("scoring", {})
        reviews.append(
            {
                "review_id": path.stem.replace("afrisafebench_", ""),
                "scenario_id": str(payload.get("scenario_id", "")),
                "title": str(payload.get("title", "")),
                "country": str(payload.get("country", "")),
                "model": str(payload.get("model", "")),
                "coverage_score": float(scoring.get("coverage_score", 0) or 0),
                "missed_risks": scoring.get("missed_risks", []),
                "path": str(path),
            }
        )
    return reviews


def _find_rescored_review(scenario_id: str, model: str) -> dict[str, Any]:
    for path in sorted(_rescored_results_dir().glob("afrisafebench_*.json")):
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if (
            _is_rescored_result(payload)
            and str(payload.get("scenario_id")) == scenario_id
            and str(payload.get("model")) == model
        ):
            return payload
    raise ValueError(f"Corrected review not found for scenario {scenario_id} and model {model}.")


def generate_framework_guidance_from_rescored_review(
    *,
    scenario_id: str,
    source_model: str,
    guidance_model: str | None = None,
    k: int = 6,
) -> dict[str, Any]:
    review = _find_rescored_review(scenario_id, source_model)
    scoring = review.get("scoring", {})
    report = generate_framework_guidance_for_scenario(
        scenario_id=scenario_id,
        model=guidance_model or source_model,
        detected_risks=review.get("identified_risks", []),
        missed_risks=scoring.get("missed_risks", []),
        k=k,
    )
    report["source_review_model"] = source_model
    report["source_review_score"] = {
        "raw_score": scoring.get("raw_score", 0),
        "max_score": scoring.get("max_score", 0),
        "coverage_score": scoring.get("coverage_score", 0),
        "matched_risks": scoring.get("matched_risks", []),
        "missed_risks": scoring.get("missed_risks", []),
    }
    return report
