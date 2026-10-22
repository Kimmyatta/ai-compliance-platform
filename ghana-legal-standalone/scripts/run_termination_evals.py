import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from evals.termination_evals import LEGACY_TASK, load_cases, probe_summary, rescore_report, run_case, verifier_metrics
from legal_app.atomic_claims import SYSTEM as ATOMIC_SYSTEM, TASK as ATOMIC_TASK
from legal_app.config import load_settings
from legal_app.focused_claims import FORMAT as FOCUSED_FORMAT, TASK as FOCUSED_TASK
from legal_app.intelligence import Intelligence, SYSTEM as LEGACY_SYSTEM
from legal_app.verifier import SYSTEM as VERIFIER_SYSTEM, TASK as VERIFIER_TASK, VERSION as VERIFIER_VERSION


def main():
    parser = argparse.ArgumentParser(description="Synthetic termination evals. Offline by default; no legal accuracy certification.")
    parser.add_argument("--live", action="store_true", help="Call the configured provider on synthetic fixtures; consumes tokens.")
    parser.add_argument("--workflow", choices=["legacy", "atomic", "focused", "verifier"], default="atomic")
    parser.add_argument("--split", choices=["development", "holdout", "all", "regression"], default="development")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--interval", type=float, default=60, help="Minimum seconds between live requests; default 60.")
    parser.add_argument("--rescore", type=Path, help="Re-screen an existing run offline; preserves the original artifact.")
    args = parser.parse_args()
    if args.interval < 0 or (args.limit is not None and args.limit < 1):
        parser.error("Use a nonnegative interval and a positive limit.")
    if args.rescore and args.live:
        parser.error("Rescoring never makes provider calls; omit --live.")
    if args.rescore and args.workflow == "verifier":
        parser.error("Verifier annotations are not lexical screens and cannot be rescored this way.")
    all_cases = load_cases(include_regressions=args.split == "regression")
    cases = [case for case in all_cases if args.split == "all" or case["split"] == args.split]
    if args.limit:
        cases = cases[:args.limit]
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "workflow": args.workflow,
              "mode": "live" if args.live else "offline_fixture_check", "split": args.split,
              "selected_cases": [case["id"] for case in cases], "fixture_count": len(all_cases),
              "fixture_sha256": hashlib.sha256(json.dumps(all_cases, sort_keys=True).encode()).hexdigest(),
              "probe_checks": probe_summary(cases), "results": [],
              "semantic_accuracy": None, "lawyer_validated": False}
    if args.rescore:
        try:
            report = rescore_report(json.loads(args.rescore.read_text(encoding="utf-8")), all_cases)
        except ValueError as exc:
            parser.error(str(exc))
        report.update(rescored_from=str(args.rescore.resolve()), rescored_at=datetime.now(timezone.utc).isoformat(),
                      fixture_sha256=hashlib.sha256(json.dumps(all_cases, sort_keys=True).encode()).hexdigest())
    elif args.live:
        settings = load_settings()
        intelligence = Intelligence(settings)
        intelligence.require_key()
        task, system = {"atomic": (ATOMIC_TASK, ATOMIC_SYSTEM), "legacy": (LEGACY_TASK, LEGACY_SYSTEM),
                        'focused': (FOCUSED_TASK, ATOMIC_SYSTEM),
                        "verifier": (VERIFIER_TASK, VERIFIER_SYSTEM)}[args.workflow]
        report.update(model=settings.model, task_prompt=task, system_prompt=system,
                      max_input_tokens=settings.max_input_tokens, max_completion_tokens=settings.max_completion_tokens)
        if args.workflow == 'focused':
            report.update(claim_format=FOCUSED_FORMAT,
                          drafting_source_sha256=hashlib.sha256((ROOT / 'backend/legal_app/focused_claims.py').read_bytes()).hexdigest())
        if args.workflow == "verifier":
            report.update(verifier_version=VERIFIER_VERSION,
                          verifier_source_sha256=hashlib.sha256((ROOT / "backend/legal_app/verifier.py").read_bytes()).hexdigest())
        earliest = 0
        for case in cases:
            time.sleep(max(0, earliest - time.monotonic()))
            start = time.monotonic()
            earliest = start + args.interval
            item = {"case": case["id"]}
            try:
                item.update(run_case(intelligence, case, args.workflow))
                delay = item.get("verification", {}).get("retry_after")
                if delay:
                    earliest = max(earliest, time.monotonic() + delay)
                item["generation_status"] = "completed"
            except HTTPException as exc:
                item.update(generation_status="failed", http_status=exc.status_code, error=exc.detail)
                if exc.status_code == 429:
                    earliest = max(earliest, time.monotonic() + int((exc.headers or {}).get("Retry-After", "60")))
            item["seconds"] = round(time.monotonic() - start, 2)
            report["results"].append(item)
            print(f"{case['id']}: {item['generation_status']}", flush=True)
    completed = [item for item in report["results"] if item["generation_status"] == "completed" and "screen" in item]
    report["screen_metrics"] = {
        "completed": len(completed), "generation_failures": len(report["results"]) - len(completed),
        "outputs_with_forbidden_pattern_flags": sum(bool(item["screen"]["forbidden_pattern_flags"]) for item in completed),
        "outputs_missing_required_patterns": sum(bool(item["screen"]["missing_required_patterns"]) for item in completed),
        "flagged_claims": sum(claim["evidence_check"] == "flagged" for item in completed for claim in item.get("checked_claims", [])),
        "meaning": "Mechanical screening counts, NOT a rate of legally correct or supported answers.",
    }
    if report["workflow"] == "verifier":
        report.pop("screen_metrics")
        report["verifier_metrics"] = verifier_metrics(report["results"])
    run_dir = ROOT / "evals" / "runs"
    run_dir.mkdir(exist_ok=True)
    path = run_dir / f"{report['workflow']}-{'rescore-' if args.rescore else ''}{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report.get("verifier_metrics", report.get("screen_metrics")), indent=2))
    print(f"Evaluation artifact: {path}")


if __name__ == "__main__":
    main()
