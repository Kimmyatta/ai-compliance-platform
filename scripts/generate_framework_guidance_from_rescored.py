import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai_safety.framework_guidance_service import (
    generate_framework_guidance_for_scenario,
)
from scripts.compile_framework_guidance_results import (
    compile_framework_guidance_results,
)


DEFAULT_INPUT_DIR = Path("data/afrisafebench/results/rescored")
DEFAULT_OUTPUT_DIR = Path("data/afrisafebench/results/framework_guidance/raw")
DEFAULT_TABLE_DIR = Path("data/afrisafebench/results")


def _is_rescored_result(payload: dict[str, Any]) -> bool:
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


def _load_rescored_results(input_dir: Path) -> list[dict[str, Any]]:
    results = []
    for path in sorted(input_dir.glob("afrisafebench_*.json")):
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if _is_rescored_result(payload):
            results.append(payload)
    return results


def _matches_filters(
    result: dict[str, Any],
    scenario_ids: set[str],
    models: set[str],
) -> bool:
    scenario_id = str(result.get("scenario_id", ""))
    model = str(result.get("model", ""))
    if scenario_ids and scenario_id not in scenario_ids:
        return False
    if models and model not in models:
        return False
    return True


def _output_path(output_dir: Path, scenario_id: str, model: str) -> Path:
    safe_model = model.replace("/", "_").replace("\\", "_")
    return output_dir / f"afrisafebench_framework_guidance_{scenario_id}_{safe_model}.json"


def generate_from_rescored(
    *,
    input_dir: Path,
    output_dir: Path,
    table_dir: Path,
    scenario_ids: set[str],
    models: set[str],
    guidance_model: str | None,
    k: int,
    limit: int | None,
    overwrite: bool,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        result
        for result in _load_rescored_results(input_dir)
        if _matches_filters(result, scenario_ids, models)
    ]
    if limit is not None:
        candidates = candidates[:limit]

    generated = 0
    skipped = 0
    outputs = []
    for result in candidates:
        scenario_id = str(result.get("scenario_id", ""))
        review_model = str(result.get("model", ""))
        model_for_guidance = guidance_model or review_model
        destination = _output_path(output_dir, scenario_id, model_for_guidance)

        if destination.exists() and not overwrite:
            skipped += 1
            outputs.append(str(destination))
            continue

        scoring = result.get("scoring", {})
        report = generate_framework_guidance_for_scenario(
            scenario_id=scenario_id,
            model=model_for_guidance,
            detected_risks=result.get("identified_risks", []),
            missed_risks=scoring.get("missed_risks", []),
            k=k,
        )
        report["source_review_model"] = review_model
        report["source_review_score"] = {
            "raw_score": scoring.get("raw_score", 0),
            "max_score": scoring.get("max_score", 0),
            "coverage_score": scoring.get("coverage_score", 0),
            "matched_risks": scoring.get("matched_risks", []),
            "missed_risks": scoring.get("missed_risks", []),
        }
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        generated += 1
        outputs.append(str(destination))

    table_summary = compile_framework_guidance_results(output_dir, table_dir)
    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "table_dir": str(table_dir),
        "candidate_count": len(candidates),
        "generated_count": generated,
        "skipped_count": skipped,
        "outputs": outputs,
        "table_summary": table_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate framework-guided reports from audited/rescored "
            "AfriSafeBench review JSON files."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument(
        "--scenario-id",
        action="append",
        default=[],
        help="Scenario ID to generate. Repeat for multiple. Empty means all.",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Source review model to use. Repeat for multiple. Empty means all.",
    )
    parser.add_argument(
        "--guidance-model",
        default=None,
        help="Model used to write framework guidance. Defaults to each source review model.",
    )
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = generate_from_rescored(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        table_dir=args.table_dir,
        scenario_ids=set(args.scenario_id),
        models=set(args.model),
        guidance_model=args.guidance_model,
        k=args.k,
        limit=args.limit,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
