import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("data/afrisafebench/results/raw")
DEFAULT_OUTPUT_DIR = Path("data/afrisafebench/results")


def _is_framework_guidance_report(payload: dict[str, Any]) -> bool:
    return all(
        key in payload
        for key in [
            "scenario_id",
            "title",
            "model",
            "framework_summary",
            "recommendations",
            "sources",
        ]
    )


def _load_reports(input_dir: Path) -> list[dict[str, Any]]:
    reports = []
    for path in sorted(input_dir.glob("afrisafebench_framework_guidance_*.json")):
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if _is_framework_guidance_report(payload):
            reports.append(payload)
    return reports


def _dedupe_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = {}
    for report in reports:
        key = (
            str(report.get("scenario_id", "")),
            str(report.get("model", "")),
        )
        deduped[key] = report
    return list(deduped.values())


def _join(values: list[str]) -> str:
    return "; ".join(value for value in values if value)


def _flatten_rows(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for report in reports:
        recommendations = report.get("recommendations", [])
        sources = report.get("sources", [])
        priority_counts = Counter(
            str(item.get("priority", "Medium")).strip().title()
            for item in recommendations
        )
        source_names = [str(source.get("source", "")) for source in sources]
        rows.append(
            {
                "scenario_id": report.get("scenario_id", ""),
                "title": report.get("title", ""),
                "country": report.get("country", ""),
                "model": report.get("model", ""),
                "framework_summary": report.get("framework_summary", ""),
                "recommendation_count": len(recommendations),
                "high_priority_count": priority_counts.get("High", 0),
                "medium_priority_count": priority_counts.get("Medium", 0),
                "low_priority_count": priority_counts.get("Low", 0),
                "recommendations": _join(
                    str(item.get("recommendation", "")) for item in recommendations
                ),
                "related_risks": _join(
                    risk
                    for item in recommendations
                    for risk in item.get("related_risks", [])
                ),
                "governance_checklist": _join(
                    str(item) for item in report.get("governance_checklist", [])
                ),
                "limitations": _join(
                    str(item)
                    for item in report.get("limitations_and_dual_use_considerations", [])
                ),
                "sources_used": _join(source_names),
                "source_count": len(source_names),
            }
        )
    return rows


def _aggregate(reports: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter()
    priority_counts = Counter()
    recommendation_counts = []

    for report in reports:
        recommendations = report.get("recommendations", [])
        recommendation_counts.append(len(recommendations))
        for source in report.get("sources", []):
            source_counts[str(source.get("source", ""))] += 1
        for recommendation in recommendations:
            priority_counts[str(recommendation.get("priority", "Medium")).strip().title()] += 1

    average_recommendations = (
        round(sum(recommendation_counts) / len(recommendation_counts), 2)
        if recommendation_counts
        else 0.0
    )
    return {
        "framework_report_count": len(reports),
        "scenario_count": len({report.get("scenario_id") for report in reports}),
        "models": sorted({report.get("model", "unknown") for report in reports}),
        "average_recommendations_per_report": average_recommendations,
        "priority_distribution": dict(priority_counts),
        "most_used_framework_sources": dict(source_counts.most_common(20)),
    }


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compile_framework_guidance_results(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = _dedupe_reports(_load_reports(input_dir))
    rows = _flatten_rows(reports)
    summary = _aggregate(reports)

    csv_path = output_dir / "framework_guidance_results.csv"
    summary_path = output_dir / "framework_guidance_summary.json"
    _write_csv(rows, csv_path)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "framework_report_count": len(reports),
        "csv_path": str(csv_path),
        "summary_path": str(summary_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile downloaded AfriSafeBench framework-guidance JSON reports."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Folder containing downloaded framework-guidance JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where framework guidance CSV and summary are written.",
    )
    args = parser.parse_args()

    summary = compile_framework_guidance_results(args.input_dir, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
