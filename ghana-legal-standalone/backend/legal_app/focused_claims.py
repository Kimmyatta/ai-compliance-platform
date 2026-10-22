"""Source-text observations and mandatory, separately checked case-application records."""

import re

from fastapi import HTTPException
from pydantic import ValidationError

from .atomic_claims import SYSTEM, check_claims, normalised
from .schemas import FocusedTerminationDraft, TerminationApplications


FORMAT = 'focused_references_v2'
TOPICS = ('notice_and_cure', 'remedial_access', 'material_breach')
TASK = """Prepare atomic claims for the focused termination issue using the evidence units.
Choose up to four descriptive observations by evidence_id and scope only. Their wording
will be copied from source text by the server, not paraphrased. Contract terms come from
contract units, current-case facts from facts units, and authority statements from authority
units. Select source propositions that matter to this case, retaining their conditions.

For EACH required application topic, align the relevant contract, facts and authority
units and choose a review-question code. notice_and_cure concerns the receipt trigger,
notice content or opportunity to remedy; remedial_access concerns the access condition
and the access evidence/dispute; material_breach concerns the materiality test and
evidence of breach. Use aligned_sources only when the selected units include relevant
contract, facts AND authority. Otherwise use evidence_gap and cite whatever relevant
units are available. Shared terminology does not establish legal consistency.
Choose only a question code provided for that topic. The server supplies its wording;
do not write an application answer, date arithmetic, legal verdict, or new quotations.
Distinguish missing detail in the confirmed summary from absence in all case files.
Observation units must be at most 500 characters; application references at most 700.
These records organize evidence for a lawyer; they never decide compliance or remedies."""

QUESTIONS = {
    'confirm_notice_receipt': 'What evidence establishes when the notice was received for the quoted cure condition?',
    'review_notice_content': 'Does the notice identify the breach described by the reviewed contract condition?',
    'review_cure_opportunity': 'Does the reviewed chronology establish the opportunity to remedy required by the quoted contract condition?',
    'review_notice_authority_scope': 'What does the cited authority establish about this notice-and-cure issue beyond the need to examine the contract?',
    'identify_access_condition': 'What do the reviewed contract terms and confirmed facts establish about access for remedial work in this case?',
    'resolve_remedial_access': 'What evidence resolves whether reasonable remedial access was provided?',
    'review_access_authority_scope': 'What, if anything, does the cited authority establish about remedial access in this case?',
    'identify_materiality_test': 'What reviewed authority supplies a test for the materiality of the alleged breach?',
    'resolve_alleged_material_breach': 'What evidence establishes the alleged breach and its materiality without treating disputed allegations as findings?',
    'review_materiality_authority_scope': 'What does the cited authority establish about material breach in this dispute?',
}

OBSERVATION_ROLES = {'contract_term': 'contract', 'case_fact': 'facts',
                     'general_principle': 'authority', 'authority_case_only': 'authority'}


def evidence_units(evidence):
    catalog = {}
    for role, original in evidence.items():
        text = normalised(original)
        # Punctuation boundaries are citation aids, not a legal or linguistic parser.
        pieces = [m.group().strip() for m in re.finditer(r'\S.*?(?:[.!?](?=\s|$)|$)', text)]
        merged = []
        for piece in pieces:
            if merged and (len(merged[-1]) < 12 or re.search(r'\b(?:a|p)\.m\.$', merged[-1], re.I)):
                merged[-1] += ' ' + piece
            else:
                merged.append(piece)
        if len(merged) > 1 and len(merged[-1]) < 12:
            merged[-2:] = [' '.join(merged[-2:])]
        offset = 0
        for index, piece in enumerate(merged, 1):
            start = text.index(piece, offset)
            unit_id = f'{role}_{index}'
            catalog[unit_id] = {'id': unit_id, 'role': role, 'text': piece, 'start': start, 'end': start + len(piece)}
            offset = start + len(piece)
    return catalog


def check_focused_draft(draft, evidence, source_ids=None):
    catalog = evidence_units(evidence)
    raw, issues, topics = [], [], []
    seen = set()
    for observation in draft['observations']:
        unit = catalog.get(observation['evidence_id'])
        if (not unit or unit['role'] != OBSERVATION_ROLES[observation['scope']] or len(unit['text']) > 500
                or unit['id'] in seen):
            raise HTTPException(502, 'The model selected an invalid or duplicate source observation. No report was generated.')
        seen.add(unit['id'])
        raw.append({'scope': observation['scope'], 'text': unit['text'],
                    'spans': [{'role': unit['role'], 'text': unit['text']}]})
        issues.append([])
        topics.append(None)
    for topic in TOPICS:
        application = draft['applications'][topic]
        spans, failures = [], []
        ids = application['evidence_ids']
        if len(set(ids)) != len(ids):
            failures.append('invalid_evidence_reference')
        for unit_id in dict.fromkeys(ids):
            unit = catalog.get(unit_id)
            if not unit or len(unit['text']) > 700:
                failures.append('invalid_evidence_reference')
            else:
                spans.append({'role': unit['role'], 'text': unit['text']})
        if application['status'] == 'aligned_sources':
            if 'facts' not in {s['role'] for s in spans}:
                failures.append('missing_case_fact_reference')
            if not {'contract', 'authority'}.issubset({s['role'] for s in spans}):
                failures.append('missing_required_role')
        raw.append({'scope': 'not_established', 'text': QUESTIONS[application['question']], 'spans': spans})
        issues.append(failures)
        topics.append(topic)
    claims = check_claims({'claims': raw}, evidence, source_ids)
    for claim, failures, topic in zip(claims, issues, topics):
        claim['wording_origin'] = 'review_question' if topic else 'source_text'
        if topic:
            claim['application_topic'] = topic
            claim['application_alignment'] = draft['applications'][topic]['status']
            claim['review_question_id'] = draft['applications'][topic]['question']
        if failures:
            claim['check_issues'] = list(dict.fromkeys([*claim['check_issues'], *failures]))
            claim['evidence_check'] = 'flagged'
    return claims


def generate_focused_claims(intelligence, facts, contract, authority, metadata=None, source_ids=None, case_basis=None):
    evidence = {'facts': facts, 'contract': contract, 'authority': authority}
    catalog = evidence_units(evidence)
    data = {'evidence_units': list(catalog.values()), 'authority_metadata': metadata or {}}
    if case_basis:
        data['factual_basis'] = 'Uploaded case-document excerpts, not the entered summary or independently proven facts.'
        data['topic_fact_candidates'] = {topic: [unit['id'] for unit in catalog.values()
            if unit['role'] == 'facts' and any(unit['text'] in source['text'] for source in case_basis['units']
                if source['id'] in case_basis['topics'][topic])] for topic in TOPICS}
    try:
        draft = FocusedTerminationDraft.model_validate(intelligence.generate(TASK,
            data,
            FocusedTerminationDraft, reasoning_effort='medium', system=SYSTEM)).model_dump()
    except ValidationError as exc:
        raise HTTPException(502, 'The model did not return all required case-application topics. No report was generated.') from exc
    return check_focused_draft(draft, evidence, source_ids), evidence


def restore_application_checks(claims, original):
    topics = [claim.get('application_topic') for claim in original if claim.get('application_topic')]
    if sorted(topics) != sorted(TOPICS):
        raise HTTPException(409, 'This focused report has incomplete case-application metadata; regenerate it first.')
    for claim, saved in zip(claims, original):
        origin = saved.get('wording_origin')
        if origin == 'source_text':
            if len(claim['spans']) != 1 or normalised(claim['text']) != claim['spans'][0]['text']:
                raise HTTPException(409, 'A source-text observation no longer matches its quoted evidence; regenerate it first.')
            claim['wording_origin'] = origin
        topic = saved.get('application_topic')
        if not topic:
            continue
        claim['application_topic'] = topic
        claim['wording_origin'] = saved.get('wording_origin', 'model_application')
        if claim['wording_origin'] == 'review_question':
            question_id = saved.get('review_question_id')
            if question_id not in QUESTIONS or claim['text'] != QUESTIONS[question_id]:
                raise HTTPException(409, 'This review question no longer matches its versioned wording; regenerate it first.')
            try:
                TerminationApplications.model_fields[topic].annotation.model_validate({
                    'status': saved.get('application_alignment'), 'evidence_ids': [], 'question': question_id})
            except ValidationError as exc:
                raise HTTPException(409, 'This review question does not match its saved topic; regenerate it first.') from exc
            claim['review_question_id'] = question_id
        if saved.get('application_alignment'):
            claim['application_alignment'] = saved['application_alignment']
        # Invalid references are not repaired by rechecking already resolved spans.
        failures = [issue for issue in saved.get('check_issues', []) if issue in {'invalid_evidence_reference', 'missing_case_fact_reference'}]
        if (claim['scope'] == 'comparison' or saved.get('application_alignment') == 'aligned_sources') and not any(span['role'] == 'facts' for span in claim['spans']):
            failures.append('missing_case_fact_reference')
        if saved.get('application_alignment') == 'aligned_sources' and not {'contract', 'authority'}.issubset({span['role'] for span in claim['spans']}):
            failures.append('missing_required_role')
        if failures:
            claim['check_issues'] = list(dict.fromkeys([*claim['check_issues'], *failures]))
            claim['evidence_check'] = 'flagged'
    return claims
