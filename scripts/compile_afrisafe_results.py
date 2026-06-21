import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("data/afrisafebench/results/raw")
DEFAULT_OUTPUT_DIR = Path("data/afrisafebench/results")


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _load_result_files(input_dir: Path) -> list[dict[str, Any]]:
    results = []
    for path in sorted(input_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if "results" in payload and isinstance(payload["results"], list):
            results.extend(
                result for result in payload["results"] if _is_afrisafe_result(result)
            )
        elif "scenario_results" in payload and isinstance(payload["scenario_results"], list):
            results.extend(
                result for result in payload["scenario_results"] if _is_afrisafe_result(result)
            )
        elif _is_afrisafe_result(payload):
            results.append(payload)

    return results


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


def _flatten_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        scoring = result.get("scoring", {})
        review_flags = result.get("human_review_flags", [])
        row = {
            "scenario_id": result.get("scenario_id", ""),
            "title": result.get("title", ""),
            "country": result.get("country", ""),
            "healthcare_context": result.get("healthcare_context", ""),
            "risk_severity": result.get("risk_severity", ""),
            "model": result.get("model", ""),
            "raw_score": scoring.get("raw_score", 0),
            "max_score": scoring.get("max_score", 0),
            "coverage_score": scoring.get("coverage_score", 0),
            "matched_risks": "; ".join(scoring.get("matched_risks", [])),
            "missed_risks": "; ".join(scoring.get("missed_risks", [])),
            "extra_risks": "; ".join(scoring.get("extra_risks", [])),
            "needs_human_review": bool(result.get("needs_human_review") or review_flags),
            "review_notes": "; ".join(
                f"{flag.get('category', '')}: {flag.get('reason', '')}".strip(": ")
                for flag in review_flags
            ),
            "review_changed_categories": "; ".join(
                flag.get("category", "") for flag in review_flags
            ),
            "identified_risks": "; ".join(
                risk.get("risk", "") for risk in result.get("identified_risks", [])
            ),
        }

        for category, category_score in scoring.get("scores_by_category", {}).items():
            row[f"score__{category}"] = category_score.get("score", 0)

        rows.append(row)
    return rows


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[float]] = defaultdict(list)
    by_risk_category: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_country: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_severity: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for result in results:
        model = result.get("model", "unknown")
        country = result.get("country", "unknown")
        severity = result.get("risk_severity", "unknown")
        scoring = result.get("scoring", {})
        coverage_score = float(scoring.get("coverage_score", 0) or 0)

        by_model[model].append(coverage_score)
        by_country[model][country].append(coverage_score)
        by_severity[model][severity].append(coverage_score)

        for category, category_score in scoring.get("scores_by_category", {}).items():
            by_risk_category[model][category].append(
                (float(category_score.get("score", 0) or 0) / 2) * 100
            )

    return {
        "evaluation_count": len(results),
        "scenario_count": len({result.get("scenario_id") for result in results}),
        "models": sorted({result.get("model", "unknown") for result in results}),
        "mean_coverage_score_by_model": {
            model: _mean(scores) for model, scores in by_model.items()
        },
        "coverage_score_by_risk_category": {
            model: {category: _mean(scores) for category, scores in categories.items()}
            for model, categories in by_risk_category.items()
        },
        "coverage_score_by_country": {
            model: {country: _mean(scores) for country, scores in countries.items()}
            for model, countries in by_country.items()
        },
        "coverage_score_by_severity": {
            model: {severity: _mean(scores) for severity, scores in severities.items()}
            for model, severities in by_severity.items()
        },
    }


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in rows for key in row})
    preferred = [
        "scenario_id",
        "title",
        "country",
        "healthcare_context",
        "risk_severity",
        "model",
        "raw_score",
        "max_score",
        "coverage_score",
        "matched_risks",
        "missed_risks",
        "extra_risks",
        "needs_human_review",
        "review_changed_categories",
        "review_notes",
        "identified_risks",
    ]
    ordered_fieldnames = preferred + [field for field in fieldnames if field not in preferred]

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=ordered_fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compile_results(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = _load_result_files(input_dir)
    rows = _flatten_rows(results)
    summary = _aggregate(results)

    csv_path = output_dir / "benchmark_results.csv"
    summary_path = output_dir / "benchmark_summary.json"
    _write_csv(rows, csv_path)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "result_files": len(list(input_dir.glob("*.json"))),
        "evaluation_count": len(results),
        "csv_path": str(csv_path),
        "summary_path": str(summary_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile downloaded AfriSafeBench JSON results into benchmark tables."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Folder containing individual AfriSafeBench JSON result files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where benchmark_results.csv and benchmark_summary.json are written.",
    )
    args = parser.parse_args()

    summary = compile_results(args.input_dir, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
