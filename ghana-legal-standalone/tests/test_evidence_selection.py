import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from legal_app.main import create_app
from legal_app.evidence_selection import quote_parts, resolve_role_basis, role_check_input
from legal_app.schemas import FocusedTerminationDraft, PassageRoleCheck, PassageSelection, VerificationBatch
from legal_app.store import Store

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'termination_review.json').read_text(encoding='utf-8'))


class AutomaticEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name))
        self.client = TestClient(self.app)
        self.store = self.app.state.store
        self.matter = self.client.post('/api/matters', json={'name': 'Synthetic automatic matter'}).json()['id']
        self.other = self.client.post('/api/matters', json={'name': 'Other private matter'}).json()['id']
        self.contract = self.upload(FIXTURE['contract'], 'matter', self.matter)
        self.authority = self.upload(FIXTURE['authority'], 'judgment')
        self.private = self.upload('Private termination terms from another matter, never available here.', 'matter', self.other)
        self.body = {'matter_id': self.matter, 'facts': FIXTURE['facts']}
        self.choices = [
            {'source_id': self.contract['chunk_id'], 'quote': FIXTURE['contract'], 'role': 'contract_term'},
            {'source_id': self.authority['chunk_id'], 'quote': FIXTURE['authority'], 'role': 'court_reasoning'},
        ]
        self.roles = {'contract_role': 'operative_term', 'authority_role': 'court_reasoning',
                      'contract_basis_ids': ['contract_1'], 'authority_basis_ids': ['authority_1']}
        self.ai = self.app.state.intelligence
        self.ai.generate = Mock(side_effect=self.answer)
        self.selection_calls = 0

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self, text, kind, matter=''):
        response = self.client.post('/api/documents', data={'kind': kind, 'matter_id': matter, 'permission_confirmed': 'true'},
                                    files={'file': ('synthetic.txt', text.encode(), 'text/plain')})
        self.assertEqual(response.status_code, 200, response.text)
        with self.store.connect() as db:
            row = db.execute('SELECT id FROM chunks WHERE document_id=? ORDER BY id', (response.json()['id'],)).fetchone()
        return self.store.source(row['id'])

    def answer(self, task, data, schema, **kwargs):
        if schema is PassageSelection:
            self.selection_calls += 1
            return self.choices[(self.selection_calls - 1) % 2]
        if schema is PassageRoleCheck:
            return self.roles
        if schema is FocusedTerminationDraft:
            return json.loads((Path(__file__).parent / 'fixtures/focused_termination_draft.json').read_text())
        if schema is VerificationBatch:
            return {'assessments': [{'claim_id': 'C1', 'verdict': 'supported', 'reason': 'The selected contract expressly states this period.',
                    'evidence': [{'role': 'contract', 'text': 'allow fourteen days after receipt'}]}]}
        self.fail(f'Unexpected model schema: {schema}')

    def prepare(self, **updates):
        return self.client.post('/api/case-analysis/termination/prepare', json={**self.body, **updates})

    def generate(self, preview, **updates):
        return self.client.post('/api/case-analysis/termination/automatic', json={**self.body,
            'selection_id': preview['selection_id'], 'confirmed': True, **updates})

    def edit_selection(self, selection_id, **updates):
        record = self.store.evidence_selection(selection_id)
        record['payload'].update(updates)
        with self.store.connect() as db:
            db.execute('UPDATE evidence_selections SET payload=? WHERE id=?', (json.dumps(record['payload']), selection_id))

    def test_preview_is_persisted_scoped_and_not_a_report_or_human_authority_confirmation(self):
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertEqual(self.ai.generate.call_count, 3)
        self.assertEqual(self.store.reports(), [])
        self.assertEqual(preview['contract']['quote'], FIXTURE['contract'])
        self.assertEqual(preview['authority']['role'], 'court_reasoning')
        reopened = Store(Path(self.temp.name)).evidence_selection(preview['selection_id'])
        self.assertEqual(reopened['matter_id'], self.matter)
        self.assertEqual(reopened['payload']['role_check'], self.roles)
        for call in self.ai.generate.call_args_list[:2]:
            self.assertNotIn(self.private['chunk_id'], [s['chunk_id'] for s in call.args[1]['sources']])

    def test_generation_uses_saved_quotes_runs_existing_checks_and_retains_provenance(self):
        preview = self.prepare().json()
        self.ai.generate.reset_mock()
        result = self.generate(preview)
        self.assertEqual(result.status_code, 200, result.text)
        payload = result.json()['payload']
        self.assertEqual(self.ai.generate.call_count, 2)
        self.assertIs(self.ai.generate.call_args_list[0].args[2], FocusedTerminationDraft)
        self.assertEqual(payload['evidence_selection']['human_confirmed'], ['facts'])
        self.assertEqual(payload['evidence_selection']['mode'], 'ai_selected')
        self.assertEqual(payload['reviewed_evidence']['contract']['quote'], preview['contract']['quote'])
        self.assertEqual(payload['claims'][0]['semantic_status'], 'supported')
        self.assertIn(payload['evidence_selection']['warning'], payload['limitations'])
        original = self.store.report(result.json()['id'])
        verified = self.client.post(f"/api/reports/{original['id']}/verify", json={})
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()['payload']['evidence_selection'], payload['evidence_selection'])
        self.assertIn(payload['evidence_selection']['warning'], verified.json()['payload']['limitations'])
        self.assertEqual(self.store.report(original['id']), original)

    def test_confirmation_missing_id_changed_facts_and_other_matter_block_before_generation(self):
        preview = self.prepare().json()
        self.ai.generate.reset_mock()
        for update, status in [({'confirmed': False}, 422), ({'facts': FIXTURE['facts'] + ' Changed.'}, 409),
                               ({'matter_id': self.other}, 404), ({'selection_id': 'missing'}, 404),
                               ({'reasoning_confirmed': True}, 422), ({'contract': self.choices[0]}, 422)]:
            with self.subTest(update=update):
                self.assertEqual(self.generate(preview, **update).status_code, status)
        self.ai.generate.assert_not_called()

    def test_expiry_new_documents_and_source_changes_invalidate_preview(self):
        preview = self.prepare().json()
        self.edit_selection(preview['selection_id'], expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        self.ai.generate.reset_mock()
        self.assertEqual(self.generate(preview).status_code, 409)
        self.ai.generate.assert_not_called()
        preview = self.prepare().json()
        self.upload('Additional private facts concerning termination notice.', 'matter', self.matter)
        self.ai.generate.reset_mock()
        self.assertEqual(self.generate(preview).status_code, 409)
        self.ai.generate.assert_not_called()
        preview = self.prepare().json()
        with self.store.connect() as db:
            db.execute('UPDATE chunks SET text=text || ? WHERE id=?', (' Extra source context.', self.authority['chunk_id']))
        self.ai.generate.reset_mock()
        self.assertEqual(self.generate(preview).status_code, 409)
        self.ai.generate.assert_not_called()

    def test_role_disagreement_allegations_background_and_uncertainty_abstain(self):
        for role in ['party_allegation', 'background', 'uncertain', 'statutory_text']:
            with self.subTest(role=role):
                self.clear_preparations()
                self.roles['authority_role'] = role
                self.assertEqual(self.prepare().status_code, 422)
        self.roles['authority_role'] = 'court_reasoning'
        for role in ['party_description', 'uncertain']:
            self.clear_preparations()
            self.roles['contract_role'] = role
            self.assertEqual(self.prepare().status_code, 422)
        self.assertEqual(self.store.reports(), [])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_selections').fetchone()[0], 0)

    def test_selector_abstention_bad_ids_other_private_sources_and_invented_quotes_reject(self):
        original = dict(self.choices[0])
        for choice in [
            {**original, 'source_id': None, 'quote': '', 'role': 'uncertain'},
            {**original, 'source_id': self.private['chunk_id'], 'quote': self.private['text']},
            {**original, 'quote': 'The agreement allows exactly seven days after receipt.'},
            {**original, 'quote': ''}, {**original, 'quote': ' ' * 30},
        ]:
            with self.subTest(choice=choice):
                self.choices[0] = choice
                self.selection_calls = 0
                self.assertIn(self.prepare().status_code, [422, 502])
        self.assertEqual(self.store.reports(), [])

    def test_invalid_role_basis_provider_failure_and_budget_failure_do_not_save_or_retry(self):
        self.roles['authority_basis_ids'] = ['invented_excerpt']
        self.assertEqual(self.prepare().status_code, 422)
        self.clear_preparations()
        self.ai.generate.side_effect = HTTPException(429, 'Rate limit; retry later.')
        self.ai.generate.reset_mock()
        self.assertEqual(self.prepare().status_code, 429)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.ai.generate.reset_mock()
        self.assertEqual(self.prepare().status_code, 429)
        self.ai.generate.assert_not_called()
        self.expire_cooldown()
        with patch('legal_app.evidence_selection.select_sources', side_effect=HTTPException(413, 'Input budget exceeded.')):
            self.assertEqual(self.prepare().status_code, 413)
        self.ai.generate.assert_not_called()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_selections').fetchone()[0], 0)

    def expire_cooldown(self):
        with self.store.connect() as db:
            for row in db.execute('SELECT cache_key,payload FROM evidence_preparations').fetchall():
                payload = json.loads(row['payload'])
                payload['retry_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
                db.execute('UPDATE evidence_preparations SET payload=? WHERE cache_key=?', (json.dumps(payload), row['cache_key']))

    def clear_preparations(self):
        with self.store.connect() as db:
            db.execute('DELETE FROM evidence_preparations')

    def test_authority_rate_limit_resumes_after_restart_without_repeating_contract_selection(self):
        self.ai.generate.side_effect = [self.choices[0], HTTPException(429, 'PRIVATE PROVIDER BODY', headers={'Retry-After': '14'})]
        response = self.client.post('/api/case-analysis/termination/prepare', json=self.body,
                                    headers={'Origin': 'http://127.0.0.1:5175'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '14')
        self.assertIn('Retry-After', response.headers['Access-Control-Expose-Headers'])
        self.assertIn('authority selection', response.json()['detail'])
        self.assertNotIn('PRIVATE PROVIDER', response.text)
        self.assertEqual(self.ai.generate.call_count, 2)
        self.ai.generate.reset_mock()
        self.assertEqual(self.prepare().status_code, 429)
        self.ai.generate.assert_not_called()
        self.expire_cooldown()
        restarted = create_app(Path(self.temp.name))
        restarted.state.intelligence.generate = Mock(side_effect=[self.choices[1], self.roles])
        with TestClient(restarted) as client:
            resumed = client.post('/api/case-analysis/termination/prepare', json=self.body)
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.assertEqual(restarted.state.intelligence.generate.call_count, 2)
        self.assertEqual(resumed.json()['contract']['quote'], self.choices[0]['quote'])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_preparations').fetchone()[0], 0)

    def test_role_check_rate_limit_resumes_only_role_check_and_cannot_bypass_it(self):
        self.ai.generate.side_effect = [*self.choices, HTTPException(429, 'Private details', headers={'Retry-After': '3'})]
        self.assertEqual(self.prepare().status_code, 429)
        with self.store.connect() as db:
            row = db.execute('SELECT cache_key,payload FROM evidence_preparations').fetchone()
            self.assertEqual(len(json.loads(row['payload'])['completed']), 2)
            self.assertNotIn('Private details', row['payload'])
        self.ai.generate.reset_mock()
        self.assertEqual(self.generate({'selection_id': row['cache_key']}).status_code, 404)
        self.ai.generate.assert_not_called()
        self.expire_cooldown()
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {**self.roles, 'authority_role': 'party_allegation'}
        rejected = self.prepare()
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertIs(self.ai.generate.call_args.args[2], PassageRoleCheck)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_selections').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_preparations').fetchone()[0], 1)

    def test_changed_facts_and_neighbour_context_do_not_reuse_old_checkpoints(self):
        self.ai.generate.side_effect = [self.choices[0], HTTPException(429, 'Limited', headers={'Retry-After': '1'})]
        self.assertEqual(self.prepare().status_code, 429)
        self.expire_cooldown()
        self.ai.generate.reset_mock()
        self.ai.generate.side_effect = [*self.choices, self.roles]
        self.assertEqual(self.prepare(facts=FIXTURE['facts'] + ' Changed facts.').status_code, 200)
        self.assertEqual(self.ai.generate.call_count, 3)
        with self.store.connect() as db:
            db.execute('UPDATE chunks SET text=text || ? WHERE id=?', (' Additional context.', self.contract['chunk_id']))
        self.ai.generate.reset_mock()
        self.ai.generate.side_effect = [*self.choices, self.roles]
        self.assertEqual(self.prepare().status_code, 200)
        self.assertEqual(self.ai.generate.call_count, 3)

    def test_role_check_rate_limit_success_resumes_without_selecting_again(self):
        self.ai.generate.side_effect = [*self.choices, HTTPException(429, 'Limited', headers={'Retry-After': '1'})]
        self.assertEqual(self.prepare().status_code, 429)
        self.expire_cooldown()
        self.ai.generate.reset_mock()
        self.ai.generate.side_effect = [self.roles]
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertIs(self.ai.generate.call_args.args[2], PassageRoleCheck)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_selections').fetchone()[0], 1)

    def test_blank_facts_and_unknown_matter_reject_without_model_calls(self):
        self.assertEqual(self.prepare(facts=' ' * 20).status_code, 422)
        self.assertEqual(self.prepare(matter_id='missing').status_code, 404)
        self.ai.generate.assert_not_called()

    def test_actual_statute_can_be_selected_but_judgment_cannot_be_labelled_statutory_text(self):
        self.choices[1]['role'] = 'statutory_text'
        self.roles['authority_role'] = 'statutory_text'
        self.assertEqual(self.prepare().status_code, 422)
        statute = self.upload('Synthetic statute, not real law: A termination notice must be given in writing.', 'statute')
        self.choices[1] = {'source_id': statute['chunk_id'], 'quote': statute['text'], 'role': 'statutory_text'}
        self.roles['authority_basis_ids'] = ['authority_1']
        self.selection_calls = 0
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['authority']['source']['kind'], 'statute')

    def test_other_private_upload_does_not_invalidate_or_enter_preview(self):
        preview = self.prepare().json()
        self.upload('Another private termination document, not relevant to the selected matter.', 'matter', self.other)
        self.assertEqual(self.generate(preview).status_code, 200)

    def test_role_check_sees_neighbour_attribution_and_context_changes_block_generation(self):
        source = self.upload('Counsel for the claimant submitted the following termination argument.\n\n'
                             + FIXTURE['authority'] + '\n\nThe court has not yet addressed that submission.', 'judgment')
        context = self.store.source_context(source)
        self.assertEqual(len(context), 2)
        quoted = context[1]
        self.choices[1] = {'source_id': quoted['chunk_id'], 'quote': quoted['text'], 'role': 'court_reasoning'}
        preview = self.prepare().json()
        call = next(call for call in self.ai.generate.call_args_list if call.args[2] is PassageRoleCheck)
        self.assertEqual(call.args[1]['authority']['context'][0]['text'], source['text'])
        with self.store.connect() as db:
            db.execute('UPDATE chunks SET text=text || ? WHERE id=?', (' Context changed.', source['chunk_id']))
        self.ai.generate.reset_mock()
        self.assertEqual(self.generate(preview).status_code, 409)
        self.ai.generate.assert_not_called()

    def test_invalid_model_structure_and_empty_collections_fail_without_successful_preview(self):
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {'bad': 'format'}
        self.assertEqual(self.prepare().status_code, 502)
        self.ai.generate.reset_mock()
        with patch('legal_app.evidence_selection.evidence_candidates', return_value={'case_passages': [], 'authority_passages': []}):
            self.assertEqual(self.prepare().status_code, 422)
        self.ai.generate.assert_not_called()

    def test_blocked_review_returns_specific_reasons_and_exact_candidates_without_passing_gate(self):
        self.roles.update(contract_role='party_description', authority_role='party_allegation', authority_basis_ids=['invented_excerpt'])
        response = self.prepare()
        self.assertEqual(response.status_code, 422)
        detail = response.json()['detail']
        self.assertEqual(detail['code'], 'evidence_role_review_required')
        review = detail['review']
        self.assertEqual({issue['code'] for issue in review['issues']}, {'contract_role_not_established', 'authority_role_disagreement', 'role_basis_not_matched'})
        self.assertEqual(review['contract']['quote'], FIXTURE['contract'])
        self.assertEqual(review['authority']['source']['chunk_id'], self.authority['chunk_id'])
        self.assertEqual(self.store.evidence_review(review['review_id'])['payload']['role_check'], self.roles)
        self.assertEqual(self.generate({'selection_id': review['review_id']}).status_code, 404)
        self.assertEqual(self.store.reports(), [])
        self.ai.generate.reset_mock()
        again = self.prepare()
        self.assertEqual(again.json(), response.json())
        self.ai.generate.assert_not_called()
        restarted = create_app(Path(self.temp.name))
        restarted.state.intelligence.generate = Mock()
        with TestClient(restarted) as client:
            self.assertEqual(client.post('/api/case-analysis/termination/prepare', json=self.body).json(), response.json())
        restarted.state.intelligence.generate.assert_not_called()

    def manual_payload(self, review):
        return {**self.body, 'role_review_id': review['review_id'], 'confirmed': True, 'reasoning_confirmed': True,
                **{role: {'source_id': review[role]['source']['chunk_id'], 'quote': review[role]['quote']} for role in ('contract', 'authority')}}

    def test_manual_recovery_requires_both_confirmations_and_keeps_original_role_flags(self):
        self.roles['authority_role'] = 'uncertain'
        review = self.prepare().json()['detail']['review']
        body = self.manual_payload(review)
        self.ai.generate.reset_mock()
        for flag in ['confirmed', 'reasoning_confirmed']:
            self.assertEqual(self.client.post('/api/case-analysis/termination', json={**body, flag: False}).status_code, 422)
        self.ai.generate.assert_not_called()
        result = self.client.post('/api/case-analysis/termination', json=body)
        self.assertEqual(result.status_code, 200, result.text)
        provenance = result.json()['payload']['evidence_selection']
        self.assertEqual(provenance['mode'], 'manual_after_role_flag')
        self.assertEqual(provenance['original_issues'], review['issues'])
        self.assertEqual(provenance['original_role_check']['authority_role'], 'uncertain')
        self.assertTrue(provenance['quotes_unchanged'])
        self.assertFalse(provenance['facts_changed'])
        original = self.store.report(result.json()['id'])
        verified = self.client.post(f"/api/reports/{original['id']}/verify", json={})
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()['payload']['evidence_selection'], provenance)
        self.assertEqual(self.store.report(original['id']), original)

    def test_manual_recovery_rejects_other_matter_bad_quotes_expiry_and_changed_context(self):
        self.roles['authority_role'] = 'uncertain'
        review = self.prepare().json()['detail']['review']
        body = self.manual_payload(review)
        self.ai.generate.reset_mock()
        self.assertEqual(self.client.post('/api/case-analysis/termination', json={**body, 'matter_id': self.other}).status_code, 404)
        bad = {**body, 'authority': {'source_id': self.authority['chunk_id'], 'quote': 'Invented court reasoning not in this passage.'}}
        self.assertEqual(self.client.post('/api/case-analysis/termination', json=bad).status_code, 422)
        record = self.store.evidence_review(review['review_id'])
        expired = {**record['payload'], 'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
        with self.store.connect() as db:
            db.execute('UPDATE evidence_reviews SET payload=? WHERE id=?', (json.dumps(expired), review['review_id']))
        self.assertEqual(self.client.post('/api/case-analysis/termination', json=body).status_code, 409)
        with self.store.connect() as db:
            db.execute('UPDATE evidence_reviews SET payload=? WHERE id=?', (json.dumps(record['payload']), review['review_id']))
            db.execute('UPDATE chunks SET text=text || ? WHERE id=?', (' Changed attribution.', self.authority['chunk_id']))
        self.assertEqual(self.client.post('/api/case-analysis/termination', json=body).status_code, 409)
        self.ai.generate.assert_not_called()

    def test_manual_corrections_are_recorded_not_claimed_as_the_original_selected_quotes(self):
        self.roles['authority_role'] = 'uncertain'
        review = self.prepare().json()['detail']['review']
        body = self.manual_payload(review)
        body['facts'] += ' User correction.'
        body['authority']['quote'] = "This termination clause will allow for such termination by either party."
        result = self.client.post('/api/case-analysis/termination', json=body)
        self.assertEqual(result.status_code, 200, result.text)
        provenance = result.json()['payload']['evidence_selection']
        self.assertFalse(provenance['quotes_unchanged'])
        self.assertTrue(provenance['facts_changed'])
        self.assertEqual(provenance['original_selected_evidence']['authority']['quote'], FIXTURE['authority'])

    def test_role_proof_references_resolve_to_exact_server_text_not_model_written_keywords(self):
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.text)
        record = self.store.evidence_selection(response.json()['selection_id'])['payload']
        self.assertEqual(record['role_check_format'], 'server_quote_parts_v1')
        for role in ('contract', 'authority'):
            text = ' '.join(record[role]['quote'].split())
            for part in record['role_evidence'][role]:
                self.assertEqual(text[part['start']:part['end']], part['text'])
                self.assertEqual(part['source_id'], record[role]['source']['chunk_id'])
        call = next(call for call in self.ai.generate.call_args_list if call.args[2] is PassageRoleCheck)
        self.assertIn('quote_parts', call.args[1]['contract'])
        self.assertNotIn('quote', call.args[1]['contract'])
        self.assertNotIn('contract_basis', PassageRoleCheck.model_json_schema()['properties'])

    def test_unknown_cross_role_duplicate_empty_and_keyword_ids_fail_closed(self):
        for ids in [['invented_excerpt'], ['authority_1'], ['contract_1', 'contract_1'], [],
                    ['shall investigate, give written notice, allow fourteen days, remedy, termination']]:
            with self.subTest(ids=ids):
                self.clear_preparations()
                self.roles['contract_basis_ids'] = ids
                response = self.prepare()
                self.assertEqual(response.status_code, 422)
                issues = response.json()['detail']['review']['issues']
                self.assertIn('role_basis_not_matched', [issue['code'] for issue in issues])
        self.assertEqual(self.store.reports(), [])

    def test_quote_parts_preserve_unicode_and_complete_continuous_source_text(self):
        from legal_app.atomic_claims import normalised
        text = ('Cafe\u0301 contract. \U0001f4c4 Written notice and fourteen days after receipt are required. ' * 9) + 'End.'
        parts = quote_parts('contract', text)
        self.assertEqual(' '.join(part['text'] for part in parts), normalised(text))
        for part in parts:
            self.assertEqual(normalised(text)[part['start']:part['end']], part['text'])
            self.assertGreaterEqual(len(part['text']), 12)
        contexts = {'contract': {'source_id': 1, 'quote': text, 'context': []}}
        data = role_check_input(contexts)
        self.assertEqual(data['contract']['quote_parts'], parts)
        proof = resolve_role_basis({'contract_basis_ids': [parts[-1]['id']]}, contexts)
        self.assertEqual(proof['contract'][0]['text'], parts[-1]['text'])


if __name__ == '__main__':
    unittest.main()
