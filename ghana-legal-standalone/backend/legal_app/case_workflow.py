"""Persistent local analysis jobs. Provider failures never approve a legal statement."""

import math
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from .case_evidence import BRIEF_TASK, documentary_facts, attach_document_sources
from .evidence_selection import (ROLE_TASK, SYSTEM, TASKS, choose, collection_digest, digest,
                                 role_check_input, role_context, role_issues)
from .issue_analysis import TASK as ANALYSIS_TASK, generate_issue, visible_application
from .schemas import ExtractiveCaseBrief, IssueAnalysisDraft, PassageRoleCheck, PassageSelection, VerificationBatch
from .store import new_id, now
from .termination import evidence_candidates
from .verifier import TASK as VERIFY_TASK, SYSTEM as VERIFY_SYSTEM, verify_claims


VERSION = 'case_workflow_v1'
ISSUES = [
    {'key': 'notice_and_cure', 'title': 'Written notice and opportunity to remedy',
     'queries': ['notice remedy termination', 'termination clause', 'rectify default written notice']},
    {'key': 'remedial_access', 'title': 'Access for remedial work',
     'queries': ['repair access opportunity remedy', 'rectify default good faith', 'failure refusal make available']},
    {'key': 'material_breach', 'title': 'Alleged material breach and termination',
     'queries': ['material breach termination', 'breach discharge obligations', 'defective performance termination']},
]
WARNING = ('Unverified AI draft for lawyer review. Exact source matching and a separate AI '
           'assessment do not establish factual truth, legal correctness, binding effect or current law.')


def fingerprint(intelligence, store, matter_id):
    return digest({'version': VERSION, 'collection': collection_digest(store, matter_id),
        'model': intelligence.settings.model, 'input': intelligence.settings.max_input_tokens,
        'output': intelligence.settings.max_completion_tokens,
        'prompts': [TASKS, ROLE_TASK, BRIEF_TASK, ANALYSIS_TASK, VERIFY_TASK, VERIFY_SYSTEM,
                    *[schema.model_json_schema() for schema in (IssueAnalysisDraft, ExtractiveCaseBrief,
                                                               PassageSelection, PassageRoleCheck, VerificationBatch)]]})


def public_job(store, job):
    return {**{key: job.get(key) for key in ('id', 'matter_id', 'status', 'stage', 'progress', 'message',
              'created_at', 'updated_at', 'retry_at', 'report_id')},
            'report': store.report(job['report_id']) if job.get('report_id') else None}


def create_job(intelligence, store, matter_id):
    intelligence.require_key()
    if not any(d['kind'] == 'matter' and d['matter_id'] == matter_id for d in store.documents()):
        raise HTTPException(422, 'Upload case documents to this matter first.')
    expected = fingerprint(intelligence, store, matter_id)
    with store.analysis_create_lock:
        existing = next((j for j in store.analysis_jobs(matter_id)
                         if j['fingerprint'] == expected and j['status'] in {'queued', 'running', 'paused'}), None)
        if existing:
            return existing
        job = {'id': new_id(), 'matter_id': matter_id, 'fingerprint': expected,
               'model': intelligence.settings.model,
               'status': 'queued', 'stage': 'queued', 'progress': 0, 'message': 'Analysis queued.',
               'created_at': now(), 'retry_at': None, 'completed': {}, 'issues': [], 'report_id': None}
        store.save_analysis_job(job)
        return job


def authority_candidates(store, issue):
    result = {}
    for query in issue['queries']:
        for hit in store.search(query, scope='library', limit=6):
            for source in store.source_context(hit):
                result.setdefault(source['chunk_id'], source)
    return list(result.values())


def _current(intelligence, store, job):
    if fingerprint(intelligence, store, job['matter_id']) != job['fingerprint']:
        raise HTTPException(409, 'Documents or analysis settings changed. Start a fresh analysis; saved work was not mixed with new evidence.')


def _stage(intelligence, store, job, key, message, progress, action):
    _current(intelligence, store, job)
    job.update(stage=key, message=message, progress=progress)
    store.save_analysis_job(job)
    if key not in job['completed']:
        job['completed'][key] = action()
        store.save_analysis_job(job)
    return deepcopy(job['completed'][key])


def _verify_issue(intelligence, store, job, issue, draft, contract, authority, progress):
    key = f"verify:{issue['key']}"
    previous = job['completed'].get(key, {})
    by_id = {c['id']: c for c in previous.get('claims', [])}
    claims = [deepcopy(by_id.get(c['id'], c)) for c in draft['claims']]
    pending = [c for c in claims if c.get('verification', {}).get('origin') not in {'model', 'policy_gate', 'evidence_gate'}]
    notes = list(previous.get('notes', []))
    for offset in range(0, len(pending), 4):
        _current(intelligence, store, job)
        job.update(stage=key, message=f"Checking evidence: {issue['title']}", progress=progress)
        store.save_analysis_job(job)
        checked, verification = verify_claims(intelligence, pending[offset:offset + 4], draft['evidence'],
            {'contract': contract['source']['chunk_id'], 'authority': authority['source']['chunk_id']})
        checked = attach_document_sources(checked, draft['basis'])
        updates = {c['id']: c for c in checked}
        claims = [updates.get(c['id'], c) for c in claims]
        notes.extend(verification['notes'])
        job['completed'][key] = {'claims': claims, 'notes': list(dict.fromkeys(notes))}
        store.save_analysis_job(job)
        if verification.get('retry_after'):
            raise HTTPException(429, 'Provider rate limit reached while checking the draft. Completed checks are saved.',
                                headers={'Retry-After': str(verification['retry_after'])})
    return {'claims': claims, 'notes': list(dict.fromkeys(notes))}


def _issue(intelligence, store, job, basis, issue, index, contract):
    prefix = issue['key']
    progress = 20 + (index - 1) * 24
    # The selector receives source excerpts as context, never a user summary as proof.
    request = SimpleNamespace(matter_id=job['matter_id'], facts='\n'.join(
        u['text'] for u in basis['units'] if u['id'] in basis['topics'][prefix]) or basis['text'])
    candidates = _stage(intelligence, store, job, f'candidates:{prefix}', f"Finding judgments: {issue['title']}", progress,
                        lambda: authority_candidates(store, issue))
    if not candidates:
        return {**issue, 'claims': [], 'sources': [], 'notes': ['No matching passages were retrieved from the uploaded authority library. This is not a finding that no relevant law exists.']}
    authority, coverage = _stage(intelligence, store, job, f'authority:{prefix}', f"Reviewing authority: {issue['title']}", progress + 3,
        lambda: choose(intelligence, store, 'authority', candidates, request, focus=issue['title']))
    contexts = {role: role_context(store, item) for role, item in [('contract', contract), ('authority', authority)]}
    role_check = _stage(intelligence, store, job, f'roles:{prefix}', f"Checking source attribution: {issue['title']}", progress + 5,
        lambda: PassageRoleCheck.model_validate(intelligence.generate(ROLE_TASK, role_check_input(contexts),
            PassageRoleCheck, system=SYSTEM, reasoning_effort='medium', completion_tokens=900)).model_dump())
    flags = role_issues(role_check, contract, authority)
    selected_evidence = {role: {'source_id': item['source']['chunk_id'], 'quote': item['quote']}
                         for role, item in [('contract', contract), ('authority', authority)]}
    if flags:
        return {**issue, 'claims': [], 'sources': [contract['source'], authority['source']],
                'notes': [flag['message'] for flag in flags], 'role_check': role_check, 'coverage': coverage,
                'selected_evidence': selected_evidence, 'role_contexts': contexts}
    draft = _stage(intelligence, store, job, f'draft:{prefix}', f"Comparing the cases: {issue['title']}", progress + 9,
        lambda: generate_issue(intelligence, basis, prefix, issue['title'], contract, authority, index))
    verified = _verify_issue(intelligence, store, job, issue, draft, contract, authority, progress + 16)
    return {**issue, 'claims': verified['claims'], 'sources': [contract['source'], authority['source']],
            'notes': verified['notes'], 'role_check': role_check, 'coverage': {**coverage, **draft['coverage']},
            'evidence': draft['evidence'], 'case_basis': draft['basis'],
            'selected_evidence': selected_evidence, 'role_contexts': contexts}


def assemble_report(job, brief, basis, issues):
    claims = [c for issue in issues for c in issue['claims']]
    for claim in claims:
        claim['display_state'] = ('draft_for_review' if visible_application(claim) else
            'source_excerpt' if claim['wording_origin'] == 'source_text' and claim['evidence_check'] == 'matched'
                and claim['semantic_status'] == 'supported' else
            'evidence_gap' if claim['scope'] == 'not_established' and claim['evidence_check'] != 'flagged' else 'withheld')
    sources = {s['chunk_id']: s for s in [*basis['sources'], *brief['sources'],
               *(s for issue in issues for s in issue['sources'])]}
    return {'title': 'Termination and cure - case analysis', 'workflow': VERSION, 'grounding_version': 3,
        'scope': 'Termination, notice, opportunity to remedy, remedial access and alleged material breach only. Other case issues have not been analysed.',
        'brief': brief, 'case_evidence': basis, 'issue_reports': issues, 'claims': claims,
        'findings': [], 'sources': list(sources.values()), 'analysis_job_id': job['id'],
        'analysis_metadata': {'model': job['model'], 'fingerprint': job['fingerprint'], 'human_confirmed': []},
        'limitations': [WARNING, 'Only the uploaded authority library was searched. No external case-law service or subsequent-treatment check was used.',
            'Coverage is limited to selected passages. A missing excerpt or an AI abstention does not prove that evidence or applicable law does not exist.',
            'An AI-supported comparison remains a draft for lawyer review, not an accepted legal conclusion. Unsupported or unchecked application text is withheld from the main report.',
            'No lawyer confirmation is implied by clicking Analyze Case.'], 'warning': WARNING}


def run_job(intelligence, store, job_id):
    with store.analysis_job_lock:
        job = store.analysis_job(job_id)
        if not job or job['status'] not in {'queued', 'paused'}:
            return
        if job.get('retry_at') and datetime.fromisoformat(job['retry_at']) > datetime.now(timezone.utc):
            return
        job.update(status='running', retry_at=None)
        store.save_analysis_job(job)
        try:
            _current(intelligence, store, job)
            basis = _stage(intelligence, store, job, 'case_evidence', 'Reading case documents', 4,
                           lambda: documentary_facts(store, job['matter_id']))
            sources, truncated = store.matter_passages(job['matter_id'])
            brief = _stage(intelligence, store, job, 'brief', 'Identifying facts and legal issues', 10,
                           lambda: intelligence.brief(sources, truncated))
            request = SimpleNamespace(matter_id=job['matter_id'], facts=basis['text'])
            try:
                contract, _ = _stage(intelligence, store, job, 'contract', 'Finding the operative agreement terms', 16,
                    lambda: choose(intelligence, store, 'contract', evidence_candidates(store, job['matter_id'])['case_passages'], request))
            except HTTPException as exc:
                if exc.status_code not in {422, 502}:
                    raise
                contract = None
            issues = []
            for index, issue in enumerate(ISSUES, 1):
                if not contract:
                    result = {**issue, 'claims': [], 'sources': [], 'notes': ['An operative termination-and-cure clause could not be established from the selected documents. Legal application was not generated.']}
                else:
                    key = f"issue:{issue['key']}"
                    if key in job['completed']:
                        result = deepcopy(job['completed'][key])
                    else:
                        try:
                            result = _issue(intelligence, store, job, basis, issue, index, contract)
                        except HTTPException as exc:
                            if exc.status_code not in {413, 422, 502}:
                                raise
                            result = {**issue, 'claims': [], 'sources': [], 'notes': [
                                'The selected evidence or generated structure did not pass this issue\'s checks. No legal application was accepted; other issues were processed.']}
                        job['completed'][key] = result
                        store.save_analysis_job(job)
                issues.append(result)
            _current(intelligence, store, job)
            job.update(stage='report', message='Assembling the sourced draft report', progress=96)
            store.save_analysis_job(job)
            store.finish_analysis_job(job, assemble_report(job, brief, basis, issues))
        except HTTPException as exc:
            job.update(status='stale' if exc.status_code == 409 else 'paused', message=(exc.detail if isinstance(exc.detail, str) else 'Analysis needs review before continuing.'))
            if exc.status_code == 429:
                try:
                    seconds = min(3600, max(1, math.ceil(float((exc.headers or {}).get('Retry-After', '60')))))
                except (ValueError, OverflowError):
                    seconds = 60
                job['retry_at'] = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
            store.save_analysis_job(job)
        except Exception:
            # Never expose raw provider errors, document prompts or credentials.
            job.update(status='paused', message='Analysis could not complete. Completed steps are saved; resume or check the local API.')
            store.save_analysis_job(job)
