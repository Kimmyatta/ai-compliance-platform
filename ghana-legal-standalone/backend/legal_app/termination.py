from copy import deepcopy

from fastapi import HTTPException
from pydantic import ValidationError
from .atomic_claims import check_claims, normalised
from .focused_claims import FORMAT, generate_focused_claims, restore_application_checks
from .case_evidence import documentary_facts, attach_document_sources, validate_saved_basis
from .schemas import AtomicTerminationDraft, TerminationRequest
from .verifier import verify_claims


ISSUE = "Termination, written notice and opportunity to remedy breach"
SEARCH = "termination terminate notice remedy cure breach"
LIMITATIONS = [
    "Only the reviewed quotations and confirmed factual premise were assessed. Other clauses and authorities may change the analysis.",
    "Matched spans prove text occurrence only. AI verifier labels are fallible model assessments, not independent legal validation or lawyer approval.",
    "Flagged, contradicted and unchecked claims remain visible. Claim atomicity, legal support, current precedent status and any inference require lawyer review.",
    "This is an unverified AI draft, not a determination of valid termination or a recommendation to act.",
]


def evidence_candidates(store, matter_id):
    def expand(sources):
        result = {}
        for source in sources:
            # Show complete neighbouring passages for review, without changing their text.
            for neighbour in store.source_context(source):
                result.setdefault(neighbour["chunk_id"], neighbour)
        return list(result.values())

    case = expand(store.search(SEARCH, matter_id, "matter", limit=6))
    authority_hits = {}
    for query in ("unilateral termination", "termination clause", "notice remedy", "cure"):
        for source in store.search(query, scope="library", limit=6):
            authority_hits.setdefault(source["chunk_id"], source)
    authorities = expand(list(authority_hits.values()))
    return {"case_passages": case, "authority_passages": authorities,
            "coverage": "Keyword-selected passages and immediate neighbours only; not a full-file or exhaustive legal review."}


def reviewed_source(store, selection, matter_id, role):
    source = store.source(selection.source_id)
    document = store.document(source["document_id"]) if source else None
    valid = document and (document["kind"] == "matter" and document["matter_id"] == matter_id
                          if role == "contract" else document["kind"] in {"judgment", "statute"})
    if not valid:
        raise HTTPException(422, f"Select a {role} passage from the correct document collection.")
    if len(normalised(selection.quote)) < 20 or normalised(selection.quote) not in normalised(source["text"]):
        raise HTTPException(422, f"The reviewed {role} quotation must match its source exactly; do not paraphrase or splice passages.")
    return source


def compare_termination(intelligence, store, request, evidence_selection=None):
    if not request.confirmed or (evidence_selection is None and not request.reasoning_confirmed):
        raise HTTPException(422, "Review the facts, contract quotation and authority reasoning before comparison.")
    if len(request.facts.strip()) < 10:
        raise HTTPException(422, "Enter the reviewed facts for this termination issue.")
    contract = reviewed_source(store, request.contract, request.matter_id, "contract")
    authority = reviewed_source(store, request.authority, request.matter_id, "authority")
    basis = documentary_facts(store, request.matter_id)
    claims, evidence = generate_focused_claims(intelligence, basis['text'], request.contract.quote,
        request.authority.quote, {key: authority[key] for key in ("title", "court", "citation", "locator")},
        {"contract": contract["chunk_id"], "authority": authority["chunk_id"]}, case_basis=basis)
    claims = attach_document_sources(claims, basis)
    claims, verification = verify_claims(intelligence, claims, evidence,
        {"contract": contract["chunk_id"], "authority": authority["chunk_id"]})
    claims = attach_document_sources(claims, basis)
    result = {"title": "Termination and cure - atomic evidence review", "grounding_version": 2,
            "workflow": "termination_atomic_v2", "claims": claims, "verification": verification,
            "claim_format": FORMAT,
            "case_evidence": basis,
            "evidence_texts": {role: normalised(text) for role, text in evidence.items()},
            "reviewed_evidence": {"contract": request.contract.model_dump(), "authority": request.authority.model_dump()},
            "confirmed_facts": request.facts, "confirmed_issues": [ISSUE], "findings": [],
            "sources": list({s['chunk_id']: s for s in [contract, authority, *basis['sources']]}.values()),
            "limitations": [*LIMITATIONS, basis['warning']]}
    if evidence_selection is not None:
        result['evidence_selection'] = evidence_selection
        result['limitations'] = [*result['limitations'], evidence_selection['warning']]
    return result


def reverify_report(intelligence, store, report):
    payload = deepcopy(report["payload"])
    if report["kind"] != "case_analysis" or payload.get("workflow") != "termination_atomic_v2":
        raise HTTPException(409, "Only atomic-claim reports can be verified without regenerating the draft.")
    try:
        request = TerminationRequest.model_validate({"matter_id": report["matter_id"], "facts": payload["confirmed_facts"],
            **payload["reviewed_evidence"], "confirmed": True, "reasoning_confirmed": True})
        draft = AtomicTerminationDraft.model_validate({"claims": payload["claims"]}).model_dump()
    except (KeyError, ValidationError) as exc:
        raise HTTPException(409, "This saved report lacks valid reviewed evidence or atomic claims; regenerate it first.") from exc
    sources = {role: reviewed_source(store, getattr(request, role), request.matter_id, role) for role in ("contract", "authority")}
    basis = payload.get('case_evidence')
    if basis:
        validate_saved_basis(store, request.matter_id, basis)
    evidence = {"contract": request.contract.quote, "authority": request.authority.quote,
                "facts": basis['text'] if basis else request.facts}
    source_ids = {role: source["chunk_id"] for role, source in sources.items()}
    claims = check_claims(draft, evidence, source_ids)
    if payload.get('claim_format') == FORMAT:
        claims = restore_application_checks(claims, payload['claims'])
    if basis:
        claims = attach_document_sources(claims, basis)
    payload["claims"], payload["verification"] = verify_claims(intelligence, claims, evidence, source_ids)
    if basis:
        payload['claims'] = attach_document_sources(payload['claims'], basis)
    payload["evidence_texts"] = {role: normalised(text) for role, text in evidence.items()}
    payload["sources"] = list({s['chunk_id']: s for s in [*sources.values(), *(basis['sources'] if basis else [])]}.values())
    payload["limitations"] = [*LIMITATIONS, *([basis['warning']] if basis else [])]
    if payload.get('evidence_selection'):
        payload['limitations'] = [*payload['limitations'], payload['evidence_selection']['warning']]
    payload["verified_from_report_id"] = report["id"]
    return payload
