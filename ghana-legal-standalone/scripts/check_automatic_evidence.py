"""Small synthetic selection/role smoke test; never reads private matter documents."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from legal_app.config import load_settings
from legal_app.evidence_selection import ROLE_TASK, SYSTEM, prepare_evidence, role_check_input, role_context
from legal_app.intelligence import Intelligence
from legal_app.schemas import AutomaticEvidenceRequest, PassageRoleCheck
from legal_app.store import Store


def add(store, text, kind, matter_id=None):
    content = text.encode()
    return store.add_document({'filename': 'synthetic.txt', 'title': 'Synthetic role-check fixture, not real authority',
        'kind': kind, 'matter_id': matter_id, 'court': '', 'citation': 'SYNTHETIC TEST ONLY', 'decision_date': '',
        'source_url': '', 'permission_note': 'Engineering test fixture, not legal advice.',
        'sha256': hashlib.sha256(content).hexdigest()}, content, [('Paragraph 1', text)], [('Paragraph 1', text)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Make four logical provider calls with synthetic evidence only.')
    args = parser.parse_args()
    fixture = json.loads((ROOT / 'tests/fixtures/termination_review.json').read_text(encoding='utf-8'))
    if not args.live:
        print('Offline: fixture loaded. Use --live for the bounded provider smoke test; unit/browser tests use mocks.')
        return
    with tempfile.TemporaryDirectory() as folder:
        store = Store(Path(folder))
        matter = store.create_matter({'name': 'Synthetic evidence smoke test', 'reference': '', 'description': ''})
        add(store, fixture['contract'], 'matter', matter['id'])
        add(store, fixture['authority'], 'judgment')
        allegation = 'Counsel for the claimant submitted that contracts cannot be terminated unilaterally. The court has not considered that submission in this excerpt.'
        add(store, allegation, 'judgment')
        intelligence = Intelligence(load_settings(Path(folder)))
        preview = prepare_evidence(intelligence, store, AutomaticEvidenceRequest(matter_id=matter['id'], facts=fixture['facts']))
        positive = preview['authority']['quote'] in fixture['authority']
        contract = preview['contract']
        negative = PassageRoleCheck.model_validate(intelligence.generate(ROLE_TASK,
            role_check_input({'contract': role_context(store, contract), 'authority': {'kind': 'judgment', 'source_id': 0,
                'quote': allegation, 'context': [{'chunk_id': 0, 'kind': 'judgment', 'locator': 'Paragraph 1', 'text': allegation}]}}),
            PassageRoleCheck, system=SYSTEM, reasoning_effort='medium', completion_tokens=900))
        print(json.dumps({'synthetic_selection_completed': True, 'selected_reasoning_not_allegation': positive,
                          'allegation_role': negative.authority_role,
                          'allegation_not_accepted_as_reasoning': negative.authority_role not in {'court_reasoning', 'statutory_text'},
                          'model': intelligence.settings.model,
                          'warning': 'Two synthetic checks are not a reliability estimate or lawyer validation.'}))
        if not positive or negative.authority_role in {'court_reasoning', 'statutory_text'}:
            raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except HTTPException as exc:
        # No raw provider body, prompts, credentials or private source contents.
        print(json.dumps({'completed': False, 'status': exc.status_code, 'detail': exc.detail}))
        raise SystemExit(1)
