import json
from pathlib import Path
from typing import Any

from backend.ai_safety.evaluation_service import (
    evaluate_ai_safety,
    evaluate_scenario,
    list_models,
    list_scenarios,
    run_full_benchmark,
)
from backend.ai_safety.framework_guidance_service import (
    generate_framework_guidance_from_rescored_review,
    generate_framework_guidance_for_scenario,
    list_rescored_reviews,
)
from backend.app.core.config import get_settings


def _framework_path() -> Path:
    return get_settings().project_root / "data" / "afrisafebench_frameworks.json"


def _framework_raw_dir() -> Path:
    return get_settings().project_root / "data" / "afrisafebench" / "frameworks" / "raw"


def list_frameworks() -> list[dict[str, Any]]:
    framework_path = _framework_path()
    if not framework_path.exists():
        return []
    with framework_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    frameworks = payload.get("frameworks", payload) if isinstance(payload, dict) else payload
    return [
        framework if isinstance(framework, dict) else {"name": str(framework)}
        for framework in frameworks
    ]


def list_framework_documents() -> list[str]:
    raw_dir = _framework_raw_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    return sorted(path.name for path in raw_dir.glob("*.pdf"))


def save_framework_document(filename: str, content: bytes) -> dict[str, Any]:
    if not filename.lower().endswith(".pdf"):
        raise ValueError("AfriSafeBench framework uploads must be PDF files.")

    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Invalid framework PDF filename.")

    raw_dir = _framework_raw_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / safe_name
    destination.write_bytes(content)
    return {
        "filename": safe_name,
        "path": str(destination),
        "message": "Framework PDF uploaded. Run `python scripts/build_knowledge_base.py afrisafe_frameworks` to rebuild the index.",
    }
