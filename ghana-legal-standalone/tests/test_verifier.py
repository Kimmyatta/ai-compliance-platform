import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from legal_app.atomic_claims import check_claims
from legal_app.config import Settings
from legal_app.intelligence import Intelligence
from legal_app.verifier import verify_claims


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {'contract': 'The agreement requires fourteen days after receipt to remedy a breach before termination.',
                         'authority': 'The court examined the conditions in the contractual termination provision.',
                         'facts': 'The parties dispute whether reasonable access was provided.'}
        self.draft = {'claims': [{'scope': 'contract_term', 'text': 'The cure period is fourteen days after receipt.',
                                 'spans': [{'role': 'contract', 'text': 'fourteen days after receipt'}]}]}
        self.claims = check_claims(self.draft, self.evidence, {'contract': 1, 'authority': 2})
        self.ai = Intelligence(Settings(Path('.'), 'test-key', 'openai/gpt-oss-20b', []))
        self.ai.generate = Mock(side_effect=self.support_batch)

    def support_batch(self, task, data, schema, **kwargs):
        return {'assessments': [{'claim_id': claim['claim_id'], 'evidence': [{'role': 'contract', 'text': self.evidence['contract']}],
                                'verdict': 'supported', 'reason': 'The contract expressly states the quoted receipt-triggered period.'} for claim in data['claims']]}

    def run_verifier(self, claims=None):
        return verify_claims(self.ai, self.claims if claims is None else claims, self.evidence, {'contract': 1, 'authority': 2})

    def test_supported_assessment_matches_exact_evidence_and_is_separate_from_generator_context(self):
        checked, meta = self.run_verifier()
        self.assertEqual(checked[0]['semantic_status'], 'supported')
        self.assertEqual(checked[0]['verification']['origin'], 'model')
        span = checked[0]['verification']['evidence'][0]
        self.assertEqual(self.evidence['contract'][span['start']:span['end']], span['text'])
        self.assertEqual(span['source_id'], 1)
        self.assertEqual(meta['state'], 'complete')
        self.assertEqual(meta['model_assessed'], 1)
        data = self.ai.generate.call_args.args[1]
        self.assertNotIn('semantic_status', str(data))
        self.assertNotIn('expected', data)
        self.assertEqual(self.ai.generate.call_args.kwargs['completion_tokens'], 1800)

    def test_contradicted_and_insufficient_assessments_are_retained_not_deleted(self):
        for verdict in ('contradicted', 'insufficient_evidence'):
            self.ai.generate.side_effect = None
            self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1',
                'evidence': [] if verdict == 'insufficient_evidence' else [{'role': 'contract', 'text': self.evidence['contract']}],
                'verdict': verdict, 'reason': 'The exact claim is not established by this reviewed evidence.'}]}
            checked, meta = self.run_verifier()
            self.assertEqual(len(checked), 1)
            self.assertEqual(checked[0]['text'], self.claims[0]['text'])
            self.assertEqual(checked[0]['semantic_status'], verdict)
            self.assertEqual(meta['model_assessed'], 1)

    def test_invented_verifier_quote_does_not_get_a_positive_label(self):
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'verdict': 'supported',
            'evidence': [{'role': 'contract', 'text': 'The agreement permits immediate termination without notice.'}],
            'reason': 'A fabricated quotation should not pass evidence validation.'}]}
        checked, meta = self.run_verifier()
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.assertEqual(meta['state'], 'unavailable')
        self.assertIn('withheld', checked[0]['verification']['reason'])

    def test_wrong_role_and_supported_without_evidence_are_rejected(self):
        for spans in ([], [{'role': 'authority', 'text': self.evidence['authority']}]):
            self.ai.generate.side_effect = None
            self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'verdict': 'supported',
                'evidence': spans, 'reason': 'A contract term needs contract evidence, not a different source role.'}]}
            self.assertEqual(self.run_verifier()[0][0]['semantic_status'], 'not_checked')

    def test_comparison_support_needs_both_roles_but_contradiction_can_point_to_one(self):
        draft = deepcopy(self.draft)
        draft['claims'][0]['scope'] = 'comparison'
        draft['claims'][0]['spans'].append({'role': 'authority', 'text': self.evidence['authority']})
        claims = check_claims(draft, self.evidence)
        checked, _ = self.run_verifier(claims)
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'verdict': 'contradicted',
            'evidence': [{'role': 'contract', 'text': self.evidence['contract']}],
            'reason': 'One part of the comparison conflicts with the contract wording.'}]}
        self.assertEqual(self.run_verifier(claims)[0][0]['semantic_status'], 'contradicted')

    def test_cross_source_positive_proposal_is_withheld_even_with_real_quotes(self):
        draft = deepcopy(self.draft)
        draft['claims'][0]['scope'] = 'comparison'
        draft['claims'][0]['spans'].append({'role': 'authority', 'text': self.evidence['authority']})
        claims = check_claims(draft, self.evidence)
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {'assessments': [{'claim_id': 'C1', 'verdict': 'supported',
            'evidence': [{'role': role, 'text': self.evidence[role]} for role in ('contract', 'authority')],
            'reason': 'A fallible model proposed support based on both reviewed excerpts.'}]}
        checked, meta = self.run_verifier(claims)
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.assertEqual(checked[0]['verification']['origin'], 'policy_gate')
        self.assertEqual(checked[0]['verification']['model_verdict'], 'supported')
        self.assertEqual(meta['withheld_model_support'], 1)
        self.assertEqual(meta['model_assessed'], 1)

    def test_flagged_claims_and_unresolved_points_do_not_get_sent_for_positive_verdicts(self):
        claims = deepcopy(self.claims)
        claims[0]['evidence_check'] = 'flagged'
        checked, meta = self.run_verifier(claims)
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.assertEqual(meta['blocked_claims'], 1)
        self.assertEqual(meta['state'], 'skipped')
        self.ai.generate.assert_not_called()
        unresolved = check_claims({'claims': [{'scope': 'not_established', 'text': 'Was reasonable access actually provided?', 'spans': []}]}, self.evidence)
        checked, meta = self.run_verifier(unresolved)
        self.assertEqual(checked[0]['semantic_status'], 'insufficient_evidence')
        self.assertEqual(checked[0]['verification']['origin'], 'evidence_gate')
        self.assertEqual(meta['model_assessed'], 0)

    def test_duplicate_missing_or_unknown_ids_withhold_the_entire_batch(self):
        for ids in (['UNKNOWN'], ['C1', 'C1'], []):
            self.ai.generate.side_effect = None
            self.ai.generate.return_value = {'assessments': [{'claim_id': claim_id, 'verdict': 'insufficient_evidence',
                'evidence': [], 'reason': 'The batch identifiers must match the requested claims.'} for claim_id in ids]}
            checked, meta = self.run_verifier()
            self.assertEqual(checked[0]['semantic_status'], 'not_checked')
            self.assertEqual(meta['model_assessed'], 0)

    def test_malformed_response_never_implies_success(self):
        self.ai.generate.side_effect = None
        self.ai.generate.return_value = {'claims': self.draft['claims']}
        checked, meta = self.run_verifier()
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.assertEqual(meta['state'], 'unavailable')

    def test_rate_limit_stops_remaining_batches_and_preserves_retry_delay(self):
        claims = check_claims({'claims': self.draft['claims'] * 8}, self.evidence)
        self.ai.generate.side_effect = HTTPException(429, 'PRIVATE_PROVIDER_BODY', headers={'Retry-After': '37'})
        checked, meta = self.run_verifier(claims)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertEqual(meta['retry_after'], 37)
        self.assertTrue(all(c['semantic_status'] == 'not_checked' for c in checked))
        self.assertNotIn('PRIVATE_PROVIDER_BODY', str(meta))

    def test_unavailable_provider_does_not_overwrite_the_original_claims_or_stale_labels(self):
        claims = deepcopy(self.claims)
        claims[0]['semantic_status'] = 'supported'
        before = deepcopy(claims)
        self.ai.generate.side_effect = HTTPException(503, 'PRIVATE_PROVIDER_BODY')
        checked, meta = self.run_verifier(claims)
        self.assertEqual(claims, before)
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.assertEqual(meta['state'], 'unavailable')
        self.assertNotIn('PRIVATE_PROVIDER_BODY', str(meta))

    def test_eight_claims_are_batched_in_two_calls(self):
        claims = check_claims({'claims': self.draft['claims'] * 8}, self.evidence)
        checked, meta = self.run_verifier(claims)
        self.assertEqual(self.ai.generate.call_count, 2)
        self.assertTrue(all(len(call.args[1]['claims']) <= 4 for call in self.ai.generate.call_args_list))
        self.assertEqual(meta['model_assessed'], 8)
        self.assertTrue(all(c['semantic_status'] == 'supported' for c in checked))

    def test_batch_cap_leaves_remaining_claims_unchecked(self):
        claims = check_claims({'claims': self.draft['claims'] * 8}, self.evidence)
        with patch('legal_app.verifier.BATCH_SIZE', 1):
            checked, meta = self.run_verifier(claims)
        self.assertEqual(self.ai.generate.call_count, 3)
        self.assertEqual(meta['state'], 'partial')
        self.assertEqual(sum(c['semantic_status'] == 'not_checked' for c in checked), 5)

    def test_input_budget_failure_never_clips_evidence_or_calls_model(self):
        self.ai.settings = Settings(Path('.'), 'test-key', 'openai/gpt-oss-20b', [], max_input_tokens=10)
        checked, meta = self.run_verifier()
        self.ai.generate.assert_not_called()
        self.assertEqual(meta['state'], 'unavailable')
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')

    def test_fingerprint_binds_claim_text_and_complete_evidence_not_previous_verdict(self):
        _, first = self.run_verifier()
        claims = deepcopy(self.claims)
        claims[0]['semantic_status'] = 'contradicted'
        _, second = self.run_verifier(claims)
        self.assertEqual(first['input_sha256'], second['input_sha256'])
        claims[0]['text'] = 'An altered proposition requiring a different assessment.'
        _, changed = self.run_verifier(claims)
        self.assertNotEqual(first['input_sha256'], changed['input_sha256'])


if __name__ == '__main__':
    unittest.main()
