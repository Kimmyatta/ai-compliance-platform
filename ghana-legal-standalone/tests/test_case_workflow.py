import copy
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from legal_app.case_workflow import ISSUES, create_job, run_job
from legal_app.main import create_app
from legal_app.schemas import ExtractiveCaseBrief, IssueAnalysisDraft, PassageRoleCheck, PassageSelection, VerificationBatch


CONTRACT = ('A party alleging material breach must give written notice identifying the breach and allow fourteen days '
            'after receipt to remedy it before termination. The customer shall provide reasonable access for remedial work.')
CASE = ('EHL alleges temperature defects in two units. ECS disputes the cause and says power interruptions caused the excursions.\n\n'
        "A courier record shows delivery at ECS's office on 12 August. ECS acknowledges office receipt.\n\n"
        'ECS proposed a repair visit for 20 August at 10 a.m. EHL offered access after 5 p.m. that day or on 24 August. '
        'The available email chain does not establish whether either alternative was finally agreed.\n\n'
        'Neither party has produced an acceptance certificate signed by EHL.')
AUTHORITY = ('SYNTHETIC TEST AUTHORITY, NOT REAL CASE LAW. '
             'The court examined the express written-notice condition before considering termination. '
             'The court considered remedial access and material breach on the evidence. '
             'The court dismissed the claim on the evidence in that earlier case.')


class CaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name))
        self.client = TestClient(self.app)
        self.store = self.app.state.store
        self.matter = self.client.post('/api/matters', json={'name': 'EHL ECS workflow regression'}).json()['id']
        self.other = self.client.post('/api/matters', json={'name': 'Other private case'}).json()['id']
        self.case = self.upload(CASE, 'matter', self.matter)
        self.contract = self.upload(CONTRACT, 'matter', self.matter)
        self.authority = self.upload(AUTHORITY, 'judgment')
        self.upload('Private notice received on 99 December. Never share this other case.', 'matter', self.other)
        self.ai = self.app.state.intelligence
        self.ai.require_key = Mock()
        self.ai.generate = Mock(side_effect=self.generate)
        self.wrong_roles = False
        self.bad_application = False
        self.no_support = False
        self.missing_ids = False
        self.call_log = []

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self, text, kind, matter=''):
        response = self.client.post('/api/documents', data={'kind': kind, 'matter_id': matter,
            'permission_confirmed': 'true'}, files={'file': ('workflow.txt', text.encode(), 'text/plain')})
        self.assertEqual(response.status_code, 200, response.text)
        with self.store.connect() as db:
            source_id = db.execute('SELECT id FROM chunks WHERE document_id=? ORDER BY id', (response.json()['id'],)).fetchone()['id']
        return self.store.source(source_id)

    def generate(self, task, data, schema, **kwargs):
        self.call_log.append(schema.__name__)
        self.assertNotIn('99 December', str(data))
        if schema is ExtractiveCaseBrief:
            return {'evidence_ids': [u['id'] for u in data['case_units'][:3]], 'issues': ['Termination and cure'], 'missing_information': []}
        if schema is PassageSelection:
            contract = 'operative termination' in task
            expected = self.contract if contract else self.authority
            self.assertIn(expected['chunk_id'], [s['chunk_id'] for s in data['sources']])
            return {'source_id': expected['chunk_id'], 'quote': CONTRACT if contract else AUTHORITY,
                    'role': 'contract_term' if contract else 'court_reasoning'}
        if schema is PassageRoleCheck:
            return {'contract_role': 'operative_term', 'authority_role': 'party_allegation' if self.wrong_roles else 'court_reasoning',
                    'contract_basis_ids': ['contract_1'], 'authority_basis_ids': ['authority_1']}
        if schema is IssueAnalysisDraft:
            units = data['evidence_units']
            topic = data['issue']
            term = 'access' if 'Access' in topic else 'defect' if 'material' in topic else 'courier'
            fact = next(u for u in units if u['role'] == 'facts' and term in u['text'].lower())
            authority = next(u for u in units if u['role'] == 'authority' and 'court examined' in u['text'])
            contract = next(u for u in units if u['role'] == 'contract' and ('access' if term == 'access' else 'notice') in u['text'])
            ids = [contract['id'], fact['id'], authority['id']]
            texts = {
                'similarity': 'Both reviewed excerpts address an express notice condition, without establishing compliance in this case.',
                'difference': 'The current case records disputed remedial arrangements; the quoted reasoning does not resolve that dispute.',
                'argument_for_termination': 'The party seeking termination could point to the documented notice, subject to proof of the other contractual conditions.',
                'argument_against_termination': 'The party resisting termination could dispute the opportunity to remedy, subject to review of the contractual conditions.',
                'weakness': 'The disputed arrangements limit what can be established about the opportunity to remedy from these excerpts.',
            }
            apps = {kind: {'status': 'draft', 'text': text, 'evidence_ids': ids} for kind, text in texts.items()}
            if self.bad_application:
                apps['similarity']['text'] = 'Termination is definitely valid and damages are guaranteed.'
            if self.missing_ids:
                apps['similarity']['evidence_ids'] = ['invented']
            return {'observations': [{'kind': 'reasoning', 'evidence_id': authority['id']}], 'applications': apps}
        if schema is VerificationBatch:
            return {'assessments': [{'claim_id': c['claim_id'], 'verdict': 'insufficient_evidence' if self.no_support else 'supported',
                    'reason': 'Synthetic assessor result for a workflow test, not legal validation.',
                    'evidence': [] if self.no_support else c['selected_spans'][:3]} for c in data['claims']]}
        self.fail(f'Unexpected provider schema: {schema}')

    def analyse(self):
        job = create_job(self.ai, self.store, self.matter)
        run_job(self.ai, self.store, job['id'])
        return self.store.analysis_job(job['id'])

    def test_end_to_end_one_action_saves_source_linked_report_and_keeps_comparisons_unapproved(self):
        response = self.client.post('/api/case-analysis/jobs', json={'matter_id': self.matter})
        self.assertEqual(response.status_code, 202, response.text)
        job = self.store.analysis_job(response.json()['id'])
        self.assertEqual(job['status'], 'completed', job['message'])
        report = self.store.report(job['report_id'])['payload']
        self.assertEqual(report['workflow'], 'case_workflow_v1')
        self.assertEqual(len(report['issue_reports']), 3)
        self.assertIn('12 August', report['case_evidence']['text'])
        self.assertIn('24 August', report['case_evidence']['text'])
        self.assertTrue(report['brief']['fact_excerpts'])
        self.assertTrue(any(c['display_state'] == 'draft_for_review' for c in report['claims']))
        self.assertTrue(all(c['semantic_status'] == 'not_checked' for c in report['claims'] if c['scope'] == 'comparison'))
        self.assertEqual(self.call_log.count('PassageSelection'), 4)
        self.assertEqual(self.call_log.count('PassageRoleCheck'), 3)
        self.assertEqual(self.call_log.count('IssueAnalysisDraft'), 3)
        self.assertTrue(all(s['document_id'] != self.store.matter_passages(self.other)[0][0]['document_id'] for s in report['sources']))
        self.assertEqual(self.client.get(f"/api/case-analysis/jobs/{job['id']}").json()['report']['id'], job['report_id'])

    def test_creation_is_idempotent_for_active_work_and_does_not_call_provider(self):
        first = create_job(self.ai, self.store, self.matter)
        second = create_job(self.ai, self.store, self.matter)
        self.assertEqual(first['id'], second['id'])
        self.ai.generate.assert_not_called()

    def test_rate_limit_saves_stages_and_resume_does_not_repeat_brief_or_contract(self):
        original = self.generate
        blocked = False
        def limited(task, data, schema, **kwargs):
            nonlocal blocked
            if schema is PassageRoleCheck and not blocked:
                blocked = True
                raise HTTPException(429, 'Safe rate-limit message', headers={'Retry-After': '8'})
            return original(task, data, schema, **kwargs)
        self.ai.generate.side_effect = limited
        job = self.analyse()
        self.assertEqual(job['status'], 'paused')
        self.assertTrue(job['retry_at'])
        self.assertEqual(self.store.reports(), [])
        count = self.ai.generate.call_count
        run_job(self.ai, self.store, job['id'])
        self.assertEqual(self.ai.generate.call_count, count)
        job['retry_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.store.save_analysis_job(job)
        run_job(self.ai, self.store, job['id'])
        completed = self.store.analysis_job(job['id'])
        self.assertEqual(completed['status'], 'completed', completed['message'])
        self.assertEqual(self.call_log.count('ExtractiveCaseBrief'), 1)
        self.assertEqual(self.call_log.count('PassageSelection'), 4)

    def test_verifier_rate_limit_preserves_assessed_batches_and_resumes_only_pending(self):
        original = self.generate
        verifier_calls = 0
        def limited(task, data, schema, **kwargs):
            nonlocal verifier_calls
            if schema is VerificationBatch:
                verifier_calls += 1
                if verifier_calls == 2:
                    raise HTTPException(429, 'Rate limited', headers={'Retry-After': '5'})
            return original(task, data, schema, **kwargs)
        self.ai.generate.side_effect = limited
        job = self.analyse()
        self.assertEqual(job['status'], 'paused', job['message'])
        checked = job['completed']['verify:notice_and_cure']['claims']
        self.assertEqual(sum(c.get('verification', {}).get('origin') in {'model', 'policy_gate'} for c in checked), 4)
        job['retry_at'] = None
        self.store.save_analysis_job(job)
        run_job(self.ai, self.store, job['id'])
        self.assertEqual(self.store.analysis_job(job['id'])['status'], 'completed')
        self.assertEqual(verifier_calls, 7)

    def test_restart_recovery_pauses_without_losing_completed_steps(self):
        job = create_job(self.ai, self.store, self.matter)
        job.update(status='running', completed={'sentinel': {'source_ids': [self.case['chunk_id']]}})
        self.store.save_analysis_job(job)
        self.store.recover_analysis_jobs()
        recovered = self.store.analysis_job(job['id'])
        self.assertEqual(recovered['status'], 'paused')
        self.assertEqual(recovered['completed'], job['completed'])
        self.ai.generate.assert_not_called()

    def test_collection_change_stales_work_before_any_provider_call(self):
        job = create_job(self.ai, self.store, self.matter)
        self.upload('New notice correspondence changes the matter evidence.', 'matter', self.matter)
        run_job(self.ai, self.store, job['id'])
        self.assertEqual(self.store.analysis_job(job['id'])['status'], 'stale')
        self.ai.generate.assert_not_called()
        self.assertEqual(self.store.reports(), [])

    def test_other_private_matter_change_does_not_invalidate_job(self):
        job = create_job(self.ai, self.store, self.matter)
        self.upload('A different private case has new notice evidence.', 'matter', self.other)
        run_job(self.ai, self.store, job['id'])
        self.assertEqual(self.store.analysis_job(job['id'])['status'], 'completed')

    def test_unsupported_invented_and_unchecked_application_text_is_withheld(self):
        for mode in ('unsupported', 'invalid'):
            with self.subTest(mode=mode):
                self.no_support = mode == 'unsupported'
                self.missing_ids = mode == 'invalid'
                self.bad_application = True
                job = self.analyse()
                self.assertEqual(job['status'], 'completed', job['message'])
                report = self.store.report(job['report_id'])['payload']
                self.assertTrue(all(c['display_state'] == 'withheld' for c in report['claims'] if c['report_kind'] == 'similarity'))

    def test_bad_role_check_produces_issue_gaps_not_a_failed_whole_case(self):
        self.wrong_roles = True
        job = self.analyse()
        self.assertEqual(job['status'], 'completed')
        issues = self.store.report(job['report_id'])['payload']['issue_reports']
        self.assertTrue(all(not issue['claims'] and issue['notes'] for issue in issues))
        self.assertNotIn('IssueAnalysisDraft', self.call_log)

    def test_one_issue_role_failure_does_not_hide_the_other_two_analyses(self):
        original = self.generate
        role_calls = 0
        def one_failure(task, data, schema, **kwargs):
            nonlocal role_calls
            result = original(task, data, schema, **kwargs)
            if schema is PassageRoleCheck:
                role_calls += 1
                if role_calls == 1:
                    result['authority_role'] = 'uncertain'
            return result
        self.ai.generate.side_effect = one_failure
        job = self.analyse()
        issues = self.store.report(job['report_id'])['payload']['issue_reports']
        self.assertFalse(issues[0]['claims'])
        self.assertTrue(issues[0]['notes'])
        self.assertTrue(issues[1]['claims'])
        self.assertTrue(issues[2]['claims'])

    def test_selection_cap_covers_late_pages_and_other_documents_without_crossing_matters(self):
        paragraphs = '\n\n'.join(f'Notice event on page {i} is disputed, with distinct correspondence number {i}.' for i in range(70))
        last = self.upload(paragraphs, 'matter', self.matter)
        sources, truncated = self.store.matter_passages(self.matter)
        self.assertTrue(truncated)
        self.assertEqual(len(sources), 40)
        self.assertIn(self.case['document_id'], {s['document_id'] for s in sources})
        self.assertIn(self.contract['document_id'], {s['document_id'] for s in sources})
        self.assertTrue(any(s['document_id'] == last['document_id'] and 'page 69' in s['text'] for s in sources))

    def test_public_status_never_contains_internal_checkpoints_or_provider_configuration(self):
        job = self.analyse()
        response = self.client.get(f"/api/case-analysis/jobs/{job['id']}").json()
        self.assertNotIn('completed', response)
        self.assertNotIn('fingerprint', response)
        self.assertNotIn('api_key', str(response))
        before = len(self.store.reports())
        run_job(self.ai, self.store, job['id'])
        self.assertEqual(len(self.store.reports()), before)

    def test_no_authorities_still_saves_a_case_summary_with_explicit_gaps(self):
        with self.store.connect() as db:
            db.execute('DELETE FROM passages WHERE rowid=?', (self.authority['chunk_id'],))
        job = self.analyse()
        self.assertEqual(job['status'], 'completed')
        issues = self.store.report(job['report_id'])['payload']['issue_reports']
        self.assertTrue(all('No matching passages' in issue['notes'][0] for issue in issues))

    def test_errors_are_sanitized_and_never_create_a_successful_report(self):
        self.ai.generate.side_effect = RuntimeError('PRIVATE TOKEN AND CASE PROMPT')
        job = self.analyse()
        self.assertEqual(job['status'], 'paused')
        self.assertNotIn('PRIVATE TOKEN', str(self.client.get(f"/api/case-analysis/jobs/{job['id']}").json()))
        self.assertEqual(self.store.reports(), [])

    def test_unknown_matter_job_empty_case_and_historical_reports_are_preserved(self):
        self.assertEqual(self.client.post('/api/case-analysis/jobs', json={'matter_id': 'unknown'}).status_code, 404)
        self.assertEqual(self.client.get('/api/case-analysis/jobs/missing').status_code, 404)
        empty = self.client.post('/api/matters', json={'name': 'Empty case'}).json()['id']
        self.assertEqual(self.client.post('/api/case-analysis/jobs', json={'matter_id': empty}).status_code, 422)
        old = self.store.save_report('case_analysis', self.matter, 'Old draft', {'title': 'Historical report', 'findings': []})
        payload = copy.deepcopy(old['payload'])
        self.analyse()
        self.assertEqual(self.store.report(old['id'])['payload'], payload)


if __name__ == '__main__':
    unittest.main()
