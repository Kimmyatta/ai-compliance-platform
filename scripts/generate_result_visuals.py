import json
from pathlib import Path
from textwrap import wrap


RESULTS_DIR = Path("data/afrisafebench/results")
FIGURES_DIR = Path("docs/figures")


PALETTE = {
    "teal": "#1f766d",
    "gold": "#d59f2a",
    "red": "#c94f4f",
    "blue": "#3d6fb6",
    "ink": "#17212b",
    "muted": "#607086",
    "grid": "#d8e0ea",
    "paper": "#ffffff",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _svg_header(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{PALETTE["paper"]}"/>',
    ]


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: int = 14,
    weight: str = "400",
    fill: str | None = None,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill or PALETTE["ink"]}" '
        f'text-anchor="{anchor}">{value}</text>'
    )


def _wrapped_text(x: float, y: float, value: str, width: int, line_height: int = 17) -> list[str]:
    lines = []
    for index, line in enumerate(wrap(value, width=width)):
        lines.append(_text(x, y + index * line_height, line, size=13, fill=PALETTE["muted"]))
    return lines


def _write_svg(path: Path, parts: list[str]) -> None:
    path.write_text("\n".join(parts + ["</svg>"]), encoding="utf-8")


def model_coverage_chart(summary: dict) -> None:
    values = summary["mean_coverage_score_by_model"]
    order = sorted(values, key=values.get, reverse=True)
    width, height = 900, 420
    left, top, bar_height, gap = 260, 105, 42, 30
    max_width = 520

    parts = _svg_header(width, height)
    parts.append(_text(36, 44, "Mean Coverage by Model", size=24, weight="700"))
    parts.append(
        _text(
            36,
            72,
            "AfriSafeBench benchmark: 25 scenarios x 3 models = 75 evaluations",
            size=14,
            fill=PALETTE["muted"],
        )
    )

    colors = [PALETTE["teal"], PALETTE["blue"], PALETTE["gold"]]
    for index, model in enumerate(order):
        y = top + index * (bar_height + gap)
        value = values[model]
        bar_width = max_width * (value / 100)
        parts.append(_text(36, y + 28, model, size=15, weight="700"))
        parts.append(
            f'<rect x="{left}" y="{y}" width="{max_width}" height="{bar_height}" fill="#edf2f6" rx="4"/>'
        )
        parts.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" fill="{colors[index % len(colors)]}" rx="4"/>'
        )
        parts.append(_text(left + bar_width + 12, y + 28, f"{value:.2f}%", size=15, weight="700"))

    parts.append(_text(36, 360, "Higher coverage means more expected risk categories were identified.", size=13, fill=PALETTE["muted"]))
    _write_svg(FIGURES_DIR / "model_coverage.svg", parts)


def category_weakness_chart(summary: dict) -> None:
    by_category = summary["coverage_score_by_risk_category"]
    categories = sorted({category for rows in by_category.values() for category in rows})
    averages = {
        category: sum(rows.get(category, 0) for rows in by_category.values()) / len(by_category)
        for category in categories
    }
    weakest = sorted(averages.items(), key=lambda item: item[1])[:10]

    width, height = 1000, 620
    left, top, bar_height, gap = 380, 105, 32, 18
    max_width = 500
    parts = _svg_header(width, height)
    parts.append(_text(36, 44, "Risk Categories with Lowest Average Coverage", size=24, weight="700"))
    parts.append(
        _text(
            36,
            72,
            "Average across evaluated models. Lower scores indicate harder-to-detect governance risks.",
            size=14,
            fill=PALETTE["muted"],
        )
    )

    for index, (category, value) in enumerate(weakest):
        y = top + index * (bar_height + gap)
        parts.extend(_wrapped_text(36, y + 21, category, width=38, line_height=15))
        parts.append(
            f'<rect x="{left}" y="{y}" width="{max_width}" height="{bar_height}" fill="#edf2f6" rx="4"/>'
        )
        color = PALETTE["red"] if value < 50 else PALETTE["gold"] if value < 70 else PALETTE["teal"]
        parts.append(
            f'<rect x="{left}" y="{y}" width="{max_width * (value / 100):.1f}" height="{bar_height}" fill="{color}" rx="4"/>'
        )
        parts.append(_text(left + max_width + 12, y + 22, f"{value:.1f}%", size=14, weight="700"))

    _write_svg(FIGURES_DIR / "category_weakness.svg", parts)


def framework_priority_chart(summary: dict) -> None:
    values = summary.get("priority_distribution", {})
    if not values:
        return

    width, height = 760, 360
    left, top, bar_height, gap = 210, 105, 42, 28
    max_count = max(values.values()) or 1
    max_width = 420
    parts = _svg_header(width, height)
    parts.append(_text(36, 44, "Framework Guidance Recommendation Priorities", size=24, weight="700"))
    parts.append(_text(36, 72, "Compiled from downloaded framework-guided reports.", size=14, fill=PALETTE["muted"]))

    colors = {"High": PALETTE["red"], "Medium": PALETTE["gold"], "Low": PALETTE["teal"]}
    for index, priority in enumerate(["High", "Medium", "Low"]):
        count = values.get(priority, 0)
        y = top + index * (bar_height + gap)
        parts.append(_text(36, y + 28, priority, size=16, weight="700"))
        parts.append(f'<rect x="{left}" y="{y}" width="{max_width}" height="{bar_height}" fill="#edf2f6" rx="4"/>')
        parts.append(
            f'<rect x="{left}" y="{y}" width="{max_width * (count / max_count):.1f}" height="{bar_height}" fill="{colors[priority]}" rx="4"/>'
        )
        parts.append(_text(left + max_width + 12, y + 28, str(count), size=15, weight="700"))

    _write_svg(FIGURES_DIR / "framework_priority_distribution.svg", parts)


def workflow_diagram() -> None:
    width, height = 1200, 360
    parts = _svg_header(width, height)
    parts.append(_text(36, 44, "AfriSafeBench Workflow", size=24, weight="700"))
    parts.append(_text(36, 72, "Evaluation benchmark plus framework-guided governance tool.", size=14, fill=PALETTE["muted"]))

    steps = [
        ("Scenario", "African healthcare AI deployment case"),
        ("LLM Review", "Model identifies risks and severities"),
        ("Scoring", "Matched, missed, extra risks"),
        ("Human Audit", "Flags semantic rescoring changes"),
        ("Framework Retrieval", "WHO, NIST, UNESCO, OECD, AU chunks"),
        ("Recommendations", "Governance actions and checklist"),
    ]
    box_w, box_h = 160, 96
    x0, y = 36, 145
    gap = 36
    for index, (title, subtitle) in enumerate(steps):
        x = x0 + index * (box_w + gap)
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" fill="#f7fafc" stroke="{PALETTE["grid"]}" rx="8"/>')
        parts.append(_text(x + 14, y + 32, title, size=15, weight="700"))
        parts.extend(_wrapped_text(x + 14, y + 56, subtitle, width=20, line_height=15))
        if index < len(steps) - 1:
            arrow_x = x + box_w + 8
            parts.append(f'<line x1="{arrow_x}" y1="{y + box_h / 2}" x2="{arrow_x + 20}" y2="{y + box_h / 2}" stroke="{PALETTE["muted"]}" stroke-width="2"/>')
            parts.append(f'<polygon points="{arrow_x + 20},{y + box_h / 2 - 5} {arrow_x + 30},{y + box_h / 2} {arrow_x + 20},{y + box_h / 2 + 5}" fill="{PALETTE["muted"]}"/>')

    _write_svg(FIGURES_DIR / "workflow_diagram.svg", parts)


def figure_index() -> None:
    markdown = """# AfriSafeBench Figures

Generated from benchmark and framework guidance outputs.

- [Model coverage](model_coverage.svg)
- [Risk category weakness](category_weakness.svg)
- [Framework priority distribution](framework_priority_distribution.svg)
- [Workflow diagram](workflow_diagram.svg)
"""
    (FIGURES_DIR / "README.md").write_text(markdown, encoding="utf-8")


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    benchmark_summary = _read_json(RESULTS_DIR / "benchmark_summary.json")
    framework_summary_path = RESULTS_DIR / "framework_guidance_summary.json"
    framework_summary = _read_json(framework_summary_path) if framework_summary_path.exists() else {}

    model_coverage_chart(benchmark_summary)
    category_weakness_chart(benchmark_summary)
    framework_priority_chart(framework_summary)
    workflow_diagram()
    figure_index()

    print(json.dumps({"output_dir": str(FIGURES_DIR), "figures": sorted(path.name for path in FIGURES_DIR.glob("*"))}, indent=2))


if __name__ == "__main__":
    main()
