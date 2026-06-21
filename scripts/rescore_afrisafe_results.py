import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_safety.evaluation_service import get_scenario
from backend.ai_safety.models import IdentifiedRisk
from backend.ai_safety.report_service import generate_report
from backend.ai_safety.scoring_service import score_model_output
from scripts.compile_afrisafe_results import compile_results


DEFAULT_INPUT_DIR = Path("data/afrisafebench/results/raw")
DEFAULT_OUTPUT_DIR = Path("data/afrisafebench/results/rescored")
DEFAULT_TABLE_DIR = Path("data/afrisafebench/results")


def _is_afrisafe_result(payload: dict[str, Any]) -> bool:
    return all(
        key in payload
        for key in [
            "scenario_id",
            "model",
            "identified_risks",
            "scoring",
            "expected_risk_categories",
        ]
    )


def _load_results(input_dir: Path) -> list[dict[str, Any]]:
    results = []
    for path in sorted(input_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if "results" in payload and isinstance(payload["results"], list):
            results.extend(result for result in payload["results"] if _is_afrisafe_result(result))
        elif "scenario_results" in payload and isinstance(payload["scenario_results"], list):
            results.extend(
                result for result in payload["scenario_results"] if _is_afrisafe_result(result)
            )
        elif _is_afrisafe_result(payload):
            results.append(payload)

    return results


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = {}
    for result in results:
        key = (
            str(result.get("scenario_id", "")),
            str(result.get("model", "")),
        )
        current = deduped.get(key)
        if not current:
            deduped[key] = result
            continue
        if result.get("raw_model_response") and not current.get("raw_model_response"):
            deduped[key] = result
        elif result.get("scoring", {}).get("raw_score", 0) > current.get("scoring", {}).get("raw_score", 0):
            deduped[key] = result
    return list(deduped.values())


def _rescore_result(result: dict[str, Any]) -> dict[str, Any]:
    scenario_id = str(result.get("scenario_id", ""))
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario not found for result: {scenario_id}")

    identified_risks = [
        IdentifiedRisk(
            risk=str(item.get("risk", "")),
            explanation=str(item.get("explanation", "")),
            severity=str(item.get("severity", "Medium")),
        )
        for item in result.get("identified_risks", [])
    ]
    old_scoring = result.get("scoring", {})
    old_scores_by_category = old_scoring.get("scores_by_category", {})
    old_missed = set(old_scoring.get("missed_risks", []))
    scoring = score_model_output(scenario, identified_risks)
    report = generate_report(scenario, identified_risks, scoring)

    human_review_flags = []
    for category, category_score in scoring.scores_by_category.items():
        old_score = old_scores_by_category.get(category, {}).get("score", 0)
        if (category in old_missed or old_score == 0) and category_score.score > 0:
            human_review_flags.append(
                {
                    "category": category,
                    "reason": (
                        "Score changed from missed to matched during rescoring. "
                        "Review semantic match."
                    ),
                    "old_score": old_score,
                    "new_score": category_score.score,
                    "matched_risk": category_score.matched_risk,
                }
            )

    updated = {
        **result,
        "title": scenario.title,
        "country": scenario.country,
        "healthcare_context": scenario.healthcare_context,
        "expected_risk_categories": scenario.expected_risk_categories,
        "risk_severity": scenario.risk_severity,
        "benchmark_explanation": scenario.explanation,
        "scoring": scoring.model_dump(),
        "report": report.model_dump(),
        "needs_human_review": bool(human_review_flags),
        "human_review_flags": human_review_flags,
    }
    return updated


def rescore_results(input_dir: Path, output_dir: Path, table_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = _dedupe_results(_load_results(input_dir))
    rescored = [_rescore_result(result) for result in results]

    for result in rescored:
        scenario_id = result.get("scenario_id", "unknown")
        model = str(result.get("model", "unknown")).replace("/", "_")
        output_path = output_dir / f"afrisafebench_{scenario_id}_{model}.json"
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    table_summary = compile_results(output_dir, table_dir)
    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "table_dir": str(table_dir),
        "rescored_count": len(rescored),
        "table_summary": table_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rescore existing AfriSafeBench results with the current rubric without calling Groq."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Folder containing original AfriSafeBench result JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where rescored result JSON files are written.",
    )
    parser.add_argument(
        "--table-dir",
        type=Path,
        default=DEFAULT_TABLE_DIR,
        help="Folder where benchmark_results.csv and benchmark_summary.json are regenerated.",
    )
    args = parser.parse_args()

    summary = rescore_results(args.input_dir, args.output_dir, args.table_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
