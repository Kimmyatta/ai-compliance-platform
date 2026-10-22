import json
import re
from copy import deepcopy
from pathlib import Path
from unicodedata import category, normalize

from legal_app.atomic_claims import check_claims, generate_atomic_claims
from legal_app.focused_claims import generate_focused_claims
from legal_app.schemas import AtomicTerminationDraft, TerminationDraft
from legal_app.verifier import verify_claims


ROOT = Path(__file__).resolve().parent
LEGACY_TASK = (ROOT / "legacy_termination_prompt.txt").read_text(encoding="utf-8").strip()


def load_cases(include_regressions=False):
    cases = json.loads((ROOT / "termination_cases.json").read_text(encoding="utf-8"))["cases"]
    if include_regressions:
        cases += json.loads((ROOT / "verifier_regressions.json").read_text(encoding="utf-8"))["cases"]
    ids = set()
    for case in cases:
        if case["id"] in ids or case["split"] not in {"development", "holdout", "regression"}:
            raise ValueError("Duplicate case ID or invalid evaluation split.")
        ids.add(case["id"])
        for check in [*case["required_checks"], *case["forbidden_checks"]]:
            re.compile(check["pattern"])
        for probe in case["probes"]:
            if probe["label"] not in {"supported", "contradicted", "insufficient_evidence"}:
                raise ValueError("Invalid probe annotation.")
            AtomicTerminationDraft.model_validate({"claims": [probe_claim(case, probe)]})
    return cases


def probe_claim(case, probe):
    return {"scope": probe["scope"], "text": probe["text"],
            "spans": [{"role": role, "text": case[role][:700]} for role in probe["roles"]]}


def probe_summary(cases):
    records = []
    for case in cases:
        evidence = {role: case[role] for role in ("contract", "authority", "facts")}
        for probe in case["probes"]:
            claim = check_claims({"claims": [probe_claim(case, probe)]}, evidence)[0]
            records.append({"case": case["id"], "expected_support": probe["label"],
                            "evidence_check": claim["evidence_check"], "semantic_status": claim["semantic_status"]})
    return {"probe_count": len(records),
            "unsupported_probes_with_matched_spans": sum(r["expected_support"] != "supported" and r["evidence_check"] == "matched" for r in records),
            "meaning": "Text matching can pass contradicted or unsupported claims. This is not a semantic verifier score.",
            "records": records}


def screen_text(case, text):
    text = " ".join("".join(" " if category(char) == "Pd" or char == "\u2212" else char
                            for char in normalize("NFC", text)).split())
    return {"forbidden_pattern_flags": [c["id"] for c in case["forbidden_checks"] if re.search(c["pattern"], text, re.IGNORECASE)],
            "missing_required_patterns": [c["id"] for c in case["required_checks"] if not re.search(c["pattern"], text, re.IGNORECASE)],
            "semantic_assessment": "not_performed",
            "warning": "Lexical screening only: paraphrases and negation can cause false negatives or positives. Manual assessment is required."}


def rescore_report(report, cases):
    if report.get("workflow") not in {"legacy", "atomic", "focused"}:
        raise ValueError("Verifier assessments cannot be rescored with lexical screens.")
    result = deepcopy(report)
    by_id = {case["id"]: case for case in cases}
    result["previous_fixture_sha256"] = result.get("fixture_sha256")
    for item in result["results"]:
        if item["generation_status"] != "completed":
            continue
        output = item["output"]
        text = "\n".join(claim["text"] for claim in output["claims"]) if result["workflow"] in {"atomic", "focused"} else "\n".join(
            [output[key] for key in ("similarities", "differences", "supporting_argument", "adverse_argument")] + output["unanswered_questions"])
        item["screen"] = screen_text(by_id[item["case"]], text)
    return result


def run_case(intelligence, case, workflow):
    if workflow == 'focused':
        claims, evidence = generate_focused_claims(intelligence, case['facts'], case['contract'], case['authority'],
            {'title': 'Synthetic evaluation authority - not real law'}, {'contract': 1001, 'authority': 2001})
        checked, verification = verify_claims(intelligence, claims, evidence, {'contract': 1001, 'authority': 2001})
        return {'output': {'claims': claims}, 'checked_claims': checked, 'verification': verification,
                'application_topics': [c['application_topic'] for c in checked if c.get('application_topic')],
                'screen': screen_text(case, '\n'.join(c['text'] for c in checked))}
    if workflow == "verifier":
        evidence = {role: case[role] for role in ("contract", "authority", "facts")}
        draft = {"claims": [probe_claim(case, probe) for probe in case["probes"]]}
        claims, verification = verify_claims(intelligence, check_claims(draft, evidence), evidence)
        return {"verification": verification, "verifier_probes": [
            {"text": probe["text"], "expected": probe["label"], "actual": claim["semantic_status"],
             "assessment": claim["verification"], "claim_id": claim["id"]}
            for probe, claim in zip(case["probes"], claims)]}
    if workflow == "atomic":
        draft, evidence = generate_atomic_claims(intelligence, case["facts"], case["contract"], case["authority"],
                                               {"title": "Synthetic evaluation authority - not real law"})
        claims = check_claims(draft, evidence)
        text = "\n".join(claim["text"] for claim in claims)
        return {"output": draft, "checked_claims": claims, "screen": screen_text(case, text)}
    data = {"confirmed_case_facts": case["facts"], "issue": "Termination, written notice and opportunity to remedy breach",
            "reviewed_contract": {"source_id": 1001, "quote": case["contract"]},
            "reviewed_authority": {"source_id": 2001, "quote": case["authority"],
                                   "title": "Synthetic evaluation authority - not real law", "court": "", "citation": "", "locator": "Fixture"}}
    draft = TerminationDraft.model_validate(intelligence.generate(LEGACY_TASK, data, TerminationDraft, reasoning_effort="medium")).model_dump()
    text = "\n".join([draft[key] for key in ("similarities", "differences", "supporting_argument", "adverse_argument")] + draft["unanswered_questions"])
    return {"output": draft, "screen": screen_text(case, text)}


def verifier_metrics(results):
    probes = [probe for item in results for probe in item.get("verifier_probes", [])]
    judged_rows = [{**p, "actual": p["assessment"].get("model_verdict", p["actual"])} for p in probes]
    assessed = [p for p in judged_rows if p["assessment"]["origin"] in {"model", "policy_gate"}]
    negatives = [p for p in assessed if p["expected"] != "supported"]
    positives = [p for p in assessed if p["expected"] == "supported"]
    false_accepts = sum(p["actual"] == "supported" for p in negatives)
    return {"annotated_probes": len(probes), "model_assessed": len(assessed), "unchecked": len(probes)-len(assessed),
            "coverage": len(assessed)/len(probes) if probes else None,
            "exact_label_agreement": sum(p["expected"] == p["actual"] for p in assessed)/len(assessed) if assessed else None,
            "unsupported_probes_assessed": len(negatives), "unsupported_claims_accepted": false_accepts,
            "false_acceptance_rate_on_assessed_negatives": false_accepts/len(negatives) if negatives else None,
            "supported_probes_assessed": len(positives),
            "supported_claims_flagged_or_abstained": sum(p["actual"] != "supported" for p in positives),
            "pipeline_unsupported_claims_accepted": sum(p["expected"] != "supported" and p["actual"] == "supported" for p in probes),
            "model_support_withheld_by_policy": sum(p["assessment"]["origin"] == "policy_gate" for p in probes),
            "insufficient_evidence_verdicts": sum(p["actual"] == "insufficient_evidence" for p in assessed),
            "confusion_matrix": {expected: {actual: sum(p["expected"] == expected and p["actual"] == actual for p in judged_rows)
                for actual in ("supported", "contradicted", "insufficient_evidence", "not_checked")}
                for expected in ("supported", "contradicted", "insufficient_evidence")},
            "warning": "Agreement with synthetic engineering annotations only, not expert-validated Ghanaian legal accuracy. Unchecked probes are not passes."}
