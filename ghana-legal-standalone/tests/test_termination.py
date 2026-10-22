import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from legal_app.main import create_app
from legal_app.schemas import FocusedTerminationDraft, VerificationBatch
from legal_app.focused_claims import evidence_units


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "termination_review.json").read_text(encoding="utf-8"))


class TerminationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name))
        self.client = TestClient(self.app)
        self.store = self.app.state.store
        self.matter = self.client.post('/api/matters', json={'name': 'Fictional termination review'}).json()
        self.other = self.client.post('/api/matters', json={'name': 'Other private matter'}).json()
        self.contract = self.upload(FIXTURE['contract'], 'matter', self.matter['id'])
        self.authority = self.upload(FIXTURE['authority'], 'judgment')
        self.private = self.upload('Other private termination evidence. Never share with the first matter.', 'matter', self.other['id'])
        self.payload = {'matter_id': self.matter['id'], 'facts': FIXTURE['facts'],
                        'contract': {'source_id': self.contract['chunk_id'], 'quote': FIXTURE['contract']},
                        'authority': {'source_id': self.authority['chunk_id'], 'quote': FIXTURE['authority']},
                        'confirmed': True, 'reasoning_confirmed': True}
        self.draft = json.loads((Path(__file__).parent / 'fixtures/focused_termination_draft.json').read_text())
        self.ai = self.app.state.intelligence
        self.ai.generate = Mock(return_value=self.draft)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self, text, kind, matter_id=''):
        result = self.client.post('/api/documents', data={'kind': kind, 'matter_id': matter_id,
            'permission_confirmed': 'true'}, files={'file': ('test.txt', text.encode(), 'text/plain')})
        self.assertEqual(result.status_code, 200)
        with self.store.connect() as db:
            source_id = db.execute('SELECT id FROM chunks WHERE document_id=? ORDER BY id', (result.json()['id'],)).fetchone()['id']
        return self.store.source(source_id)

    def compare(self, **updates):
        return self.client.post('/api/case-analysis/termination', json={**self.payload, **updates})

    def test_evidence_candidates_are_scoped_and_do_not_call_ai(self):
        response = self.client.post('/api/case-analysis/termination/evidence', json={'matter_id': self.matter['id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([s['chunk_id'] for s in response.json()['case_passages']], [self.contract['chunk_id']])
        self.assertTrue(all(s['kind'] != 'matter' for s in response.json()['authority_passages']))
        self.ai.generate.assert_not_called()

    def test_context_neighbours_never_cross_document_boundaries(self):
        source = self.upload('First background paragraph.\n\nTermination notice applies here.\n\nFinal reasoning paragraph.', 'judgment')
        with self.store.connect() as db:
            middle = db.execute('SELECT id FROM chunks WHERE document_id=? ORDER BY id LIMIT 1 OFFSET 1', (source['document_id'],)).fetchone()['id']
        context = self.store.source_context(self.store.source(middle))
        self.assertEqual(len(context), 3)
        self.assertTrue(all(s['document_id'] == source['document_id'] for s in context))
        candidates = self.client.post('/api/case-analysis/termination/evidence', json={'matter_id': self.matter['id']}).json()
        texts = [s['text'] for s in candidates['authority_passages']]
        self.assertIn('First background paragraph.', texts)
        self.assertIn('Final reasoning paragraph.', texts)

    def test_exact_reviewed_evidence_is_preserved_and_only_two_quotes_sent(self):
        response = self.compare()
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()['payload']
        self.assertEqual(payload['reviewed_evidence']['contract'], self.payload['contract'])
        self.assertEqual(payload['reviewed_evidence']['authority'], self.payload['authority'])
        task, data, schema = self.ai.generate.call_args_list[0].args
        self.assertIs(schema, FocusedTerminationDraft)
        self.assertEqual(self.ai.generate.call_args_list[0].kwargs['reasoning_effort'], 'medium')
        self.assertIn('atomic claims', task)
        self.assertIn(FIXTURE['contract'].split('A party')[0].strip(), ' '.join(unit['text'] for unit in data['evidence_units'] if unit['role'] == 'contract'))
        self.assertNotIn('Other private', json.dumps(data))
        self.assertEqual(len(payload['sources']), 2)
        self.assertEqual(payload['claims'][0]['evidence_check'], 'matched')
        self.assertEqual(payload['claims'][0]['semantic_status'], 'not_checked')
        self.assertEqual(payload['workflow'], 'termination_atomic_v2')
        self.assertEqual(self.client.get('/api/reports').json()[0]['payload'], payload)

    def test_confirmation_and_nonblank_facts_are_required(self):
        for update in ({'confirmed': False}, {'reasoning_confirmed': False}, {'facts': ' ' * 30}):
            with self.subTest(update=update):
                self.assertEqual(self.compare(**update).status_code, 422)
        self.ai.generate.assert_not_called()

    def test_wrong_roles_other_private_files_and_unknown_ids_reject_before_ai(self):
        for role, source in [('contract', self.authority), ('authority', self.contract), ('contract', self.private), ('authority', self.private)]:
            with self.subTest(role=role, source=source['chunk_id']):
                self.assertEqual(self.compare(**{role: {'source_id': source['chunk_id'], 'quote': source['text']}}).status_code, 422)
        self.assertEqual(self.compare(contract={'source_id': 999999, 'quote': FIXTURE['contract']}).status_code, 422)
        self.ai.generate.assert_not_called()

    def test_invented_paraphrased_spliced_and_blank_quotations_reject(self):
        for quote in ['There is no termination provision in the agreement.', FIXTURE['contract'].replace('fourteen', 'seven'),
                      "Clause 9 - Defects: ... before termination.", ' ' * 30]:
            with self.subTest(quote=quote):
                self.assertEqual(self.compare(contract={'source_id': self.contract['chunk_id'], 'quote': quote}).status_code, 422)
        self.ai.generate.assert_not_called()

    def test_pdf_line_break_normalisation_is_allowed(self):
        quote = FIXTURE['contract'].replace('written notice', 'written\nnotice')
        self.assertEqual(self.compare(contract={'source_id': self.contract['chunk_id'], 'quote': quote}).status_code, 200)

    def test_invented_span_is_retained_with_a_flag_not_shown_as_supported(self):
        self.draft['applications']['notice_and_cure'].update(status='aligned_sources', evidence_ids=['invented_reference'])
        result = self.compare()
        self.assertEqual(result.status_code, 200)
        claim = result.json()['payload']['claims'][1]
        self.assertEqual(claim['evidence_check'], 'flagged')
        self.assertIn('invalid_evidence_reference', claim['check_issues'])
        self.assertEqual(claim['spans'], [])
        self.assertEqual(claim['semantic_status'], 'not_checked')

    def test_unresolved_claim_has_no_forced_spans_or_legal_arguments(self):
        self.draft['observations'] = []
        result = self.compare()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['payload']['claims'][0]['evidence_check'], 'no_evidence')
        self.ai.generate.return_value = {'claims': []}
        self.assertEqual(self.compare().status_code, 502)

    def test_provider_failure_leaves_no_successful_report(self):
        self.ai.generate.side_effect = HTTPException(429, 'Rate limited')
        self.assertEqual(self.compare().status_code, 429)
        self.assertEqual(self.store.reports(), [])

    def test_verifier_rate_limit_saves_the_draft_without_a_false_positive_label(self):
        self.ai.generate.side_effect = [self.draft, HTTPException(429, 'Private provider text', headers={'Retry-After': '25'})]
        response = self.compare()
        self.assertEqual(response.status_code, 200)
        payload = response.json()['payload']
        self.assertEqual(payload['claims'][0]['semantic_status'], 'not_checked')
        self.assertEqual(payload['verification']['state'], 'unavailable')
        self.assertEqual(payload['verification']['retry_after'], 25)
        self.assertNotIn('Private provider text', json.dumps(payload))

    def test_verifier_success_is_stored_with_the_same_claim_text(self):
        assessment = {'assessments': [{'claim_id': 'C1', 'evidence': [{'role': 'contract', 'text': 'allow fourteen days after receipt to remedy it before termination'}],
            'verdict': 'supported', 'reason': 'The contract expressly states fourteen days after receipt.'}]}
        self.ai.generate.side_effect = [self.draft, assessment]
        payload = self.compare().json()['payload']
        self.assertEqual(payload['claims'][0]['text'], evidence_units({'contract': FIXTURE['contract']})['contract_2']['text'])
        self.assertEqual(payload['claims'][0]['semantic_status'], 'supported')
        self.assertEqual(payload['claims'][0]['verification']['origin'], 'model')
        self.assertEqual(payload['claims'][1]['verification']['origin'], 'evidence_gate')
        self.assertEqual(payload['verification']['model_assessed'], 1)

    def test_saved_report_verification_creates_a_new_record_without_regenerating_or_editing_history(self):
        original = self.compare().json()
        original_payload = original['payload']
        self.ai.generate.reset_mock()
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'evidence': [],
            'verdict': 'insufficient_evidence', 'reason': 'The exact legal inference is not established by the reviewed text.'}]}
        response = self.client.post(f"/api/reports/{original['id']}/verify", json={})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertNotEqual(result['id'], original['id'])
        self.assertEqual(result['payload']['verified_from_report_id'], original['id'])
        self.assertEqual(result['payload']['confirmed_facts'], original_payload['confirmed_facts'])
        self.assertEqual(self.store.report(original['id'])['payload'], original_payload)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertIs(self.ai.generate.call_args.args[2], VerificationBatch)

    def test_retry_verification_revalidates_private_matter_scope_before_any_model_call(self):
        original = self.compare().json()
        original['payload']['reviewed_evidence']['contract'] = {'source_id': self.private['chunk_id'], 'quote': self.private['text']}
        tampered = self.store.save_report('case_analysis', self.matter['id'], 'Synthetic invalid scope', original['payload'])
        self.ai.generate.reset_mock()
        response = self.client.post(f"/api/reports/{tampered['id']}/verify", json={})
        self.assertEqual(response.status_code, 422)
        self.ai.generate.assert_not_called()

    def test_missing_and_legacy_reports_are_not_verified(self):
        self.assertEqual(self.client.post('/api/reports/not-present/verify', json={}).status_code, 404)
        legacy = self.store.save_report('case_analysis', self.matter['id'], 'Old paragraph', {'title': 'Legacy', 'findings': []})
        self.assertEqual(self.client.post(f"/api/reports/{legacy['id']}/verify", json={}).status_code, 409)
        self.ai.generate.assert_not_called()

    def test_pre_verifier_atomic_report_can_be_upgraded_without_regeneration(self):
        current = self.compare().json()
        payload = current['payload']
        payload.pop('verification', None)
        for claim in payload['claims']:
            claim.pop('verification', None)
            claim['semantic_status'] = 'not_checked'
        old = self.store.save_report('case_analysis', self.matter['id'], current['query'], payload)
        self.ai.generate.reset_mock()
        self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'verdict': 'insufficient_evidence',
            'evidence': [], 'reason': 'This exact claim requires review against the source evidence.'}]}
        response = self.client.post(f"/api/reports/{old['id']}/verify", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['payload']['verification']['version'], 'claim_verifier_v1')
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertIs(self.ai.generate.call_args.args[2], VerificationBatch)
        self.assertNotIn('verification', self.store.report(old['id'])['payload'])

    def test_pre_application_atomic_report_is_not_rewritten_or_given_new_topics_on_verification(self):
        current = self.compare().json()
        payload = current['payload']
        payload.pop('claim_format')
        payload['claims'] = payload['claims'][:1]
        payload['claims'][0].pop('wording_origin', None)
        old = self.store.save_report('case_analysis', self.matter['id'], 'Historical atomic report', payload)
        self.ai.generate.reset_mock()
        self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'verdict': 'insufficient_evidence', 'evidence': [],
            'reason': 'Synthetic assessment of a historical draft only.'}]}
        response = self.client.post(f"/api/reports/{old['id']}/verify", json={})
        self.assertEqual(response.status_code, 200)
        result = response.json()['payload']
        self.assertNotIn('claim_format', result)
        self.assertEqual(len(result['claims']), 1)
        self.assertEqual(result['claims'][0]['text'], payload['claims'][0]['text'])
        self.assertNotIn('application_topic', result['claims'][0])
        self.assertEqual(self.store.report(old['id'])['payload'], payload)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertIs(self.ai.generate.call_args.args[2], VerificationBatch)


if __name__ == '__main__':
    unittest.main()
