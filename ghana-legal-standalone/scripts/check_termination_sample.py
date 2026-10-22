import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from legal_app.config import load_settings
from legal_app.intelligence import Intelligence
from legal_app.schemas import TerminationRequest
from legal_app.store import Store
from legal_app.termination import compare_termination, evidence_candidates, normalised, reviewed_source


def main():
    parser = argparse.ArgumentParser(description="Check the fictional termination fixture without saving a report.")
    parser.add_argument("--live", action="store_true", help="Send the verified fictional fixture to the configured AI provider.")
    args = parser.parse_args()
    fixture = json.loads((ROOT / "tests" / "fixtures" / "termination_review.json").read_text(encoding="utf-8"))
    settings = load_settings()
    store = Store(settings.data_dir)
    matter = next((m for m in store.matters() if m["reference"] == "DEMO-CONTRACT-001"), None)
    if not matter:
        parser.error("The fictional DEMO-CONTRACT-001 matter is not present in this workspace.")
    candidates = evidence_candidates(store, matter["id"])

    def find(role, sources):
        for source in sources:
            if normalised(fixture[role]) in normalised(source["text"]):
                return {"source_id": source["chunk_id"], "quote": fixture[role]}
        parser.error(f"The exact fictional fixture {role} quotation was not found. No provider request was made.")

    request = TerminationRequest(matter_id=matter["id"], facts=fixture["facts"],
        contract=find("contract", candidates["case_passages"]),
        authority=find("authority", candidates["authority_passages"]),
        confirmed=True, reasoning_confirmed=True)
    for role in ("contract", "authority"):
        source = reviewed_source(store, getattr(request, role), matter["id"], role)
        print(f"Verified {role}: {source['title']} / {source['locator']} / #{source['chunk_id']}")
    print("Fixture only: no legal certification or report saved.")
    if args.live:
        result = compare_termination(Intelligence(settings), store, request)
        print(json.dumps(result["claims"], ensure_ascii=False, indent=2))
    print("Manual review required:")
    for check in fixture["manual_review_checks"]:
        print(f"- {check}")


if __name__ == "__main__":
    main()
