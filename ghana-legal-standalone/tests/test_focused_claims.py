import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from legal_app.atomic_claims import normalised
from legal_app.focused_claims import TOPICS, check_focused_draft, evidence_units, generate_focused_claims, restore_application_checks
from legal_app.schemas import FocusedTerminationDraft
from legal_app.verifier import verify_claims


class FocusedClaimsTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            'contract': 'The supplier shall investigate defects promptly. Written notice must allow fourteen days after receipt before termination. The customer shall provide reasonable remedial access.',
            'facts': 'EHL sent notice on 10 August and terminated on 27 August, retaining all six units. The parties dispute remedial access.',
            'authority': 'In general, a termination clause sets the conditions for ending the agreement. Without such a clause, unilateral termination would typically constitute a breach.',
        }
        self.draft = json.loads((Path(__file__).parent / 'fixtures/focused_termination_draft.json').read_text())
        self.ids = {'contract': 131, 'authority': 110}

    def check(self):
        return check_focused_draft(self.draft, self.evidence, self.ids)

    def test_observations_are_source_text_and_cannot_drop_qualifications(self):
        self.draft['observations'] = [{'scope': 'general_principle', 'evidence_id': 'authority_2', 'text': 'Unilateral termination always constitutes breach.'}]
        claim = self.check()[0]
        self.assertEqual(claim['text'], 'Without such a clause, unilateral termination would typically constitute a breach.')
        self.assertEqual(claim['wording_origin'], 'source_text')
        self.assertEqual(claim['text'], claim['spans'][0]['text'])
        self.assertEqual(claim['evidence_check'], 'matched')
        self.assertEqual(claim['semantic_status'], 'not_checked')

    def test_fact_observation_keeps_comma_and_matches_without_retyping(self):
        self.draft['observations'] = [{'scope': 'case_fact', 'evidence_id': 'facts_1'}]
        claim = self.check()[0]
        self.assertIn('27 August, retaining all six units.', claim['text'])
        self.assertEqual(claim['evidence_check'], 'matched')
        self.assertIsNone(claim['spans'][0]['source_id'])
        span = claim['spans'][0]
        self.assertEqual(self.evidence['facts'][span['start']:span['end']], span['text'])

    def test_all_three_topics_are_required_by_the_model_schema(self):
        intelligence = SimpleNamespace(generate=Mock(return_value={'observations': [], 'applications': {}}))
        with self.assertRaises(HTTPException) as caught:
            generate_focused_claims(intelligence, self.evidence['facts'], self.evidence['contract'], self.evidence['authority'])
        self.assertEqual(caught.exception.status_code, 502)
        required = FocusedTerminationDraft.model_json_schema()['$defs']['TerminationApplications']['required']
        self.assertEqual(set(required), set(TOPICS))

    def test_application_text_is_a_fixed_question_not_a_model_verdict_or_date_calculation(self):
        self.draft['applications']['notice_and_cure']['text'] = 'There were fifteen days, satisfying the cure condition and making termination valid.'
        claim = self.check()[1]
        self.assertEqual(claim['text'], 'Does the reviewed chronology establish the opportunity to remedy required by the quoted contract condition?')
        self.assertEqual(claim['scope'], 'not_established')
        self.assertEqual(claim['wording_origin'], 'review_question')
        self.assertNotIn('satisfying', claim['text'])
        self.assertNotIn('text', FocusedTerminationDraft.model_json_schema()['$defs']['NoticeApplication']['properties'])

    def test_questions_cannot_swap_receipt_timing_into_the_access_topic(self):
        self.draft['applications']['remedial_access']['question'] = 'confirm_notice_receipt'
        intelligence = SimpleNamespace(generate=Mock(return_value=self.draft))
        with self.assertRaises(HTTPException) as caught:
            generate_focused_claims(intelligence, self.evidence['facts'], self.evidence['contract'], self.evidence['authority'])
        self.assertEqual(caught.exception.status_code, 502)

    def test_unresolved_application_is_a_required_case_topic_not_a_positive_conclusion(self):
        self.draft['observations'] = []
        claims = self.check()
        self.assertEqual([c['application_topic'] for c in claims], list(TOPICS))
        intelligence = SimpleNamespace(generate=Mock(), settings=SimpleNamespace(model='openai/gpt-oss-20b', max_input_tokens=4000))
        checked, info = verify_claims(intelligence, claims, self.evidence, self.ids)
        intelligence.generate.assert_not_called()
        self.assertEqual(info['gate_assessed'], 3)
        self.assertTrue(all(c['semantic_status'] == 'insufficient_evidence' for c in checked))

    def test_comparison_needs_confirmed_facts_as_well_as_contract_and_authority(self):
        application = self.draft['applications']['notice_and_cure']
        application.update(status='aligned_sources', evidence_ids=['contract_2', 'authority_1'])
        claim = self.check()[1]
        self.assertIn('missing_case_fact_reference', claim['check_issues'])
        self.assertEqual(claim['evidence_check'], 'flagged')
        application['evidence_ids'].append('facts_1')
        self.assertEqual(self.check()[1]['evidence_check'], 'matched')

    def test_invalid_duplicate_or_overlong_application_references_are_retained_flagged(self):
        for ids in [['missing'], ['contract_2', 'contract_2']]:
            with self.subTest(ids=ids):
                self.draft['applications']['notice_and_cure']['evidence_ids'] = ids
                claim = self.check()[1]
                self.assertIn('invalid_evidence_reference', claim['check_issues'])
                self.assertEqual(claim['evidence_check'], 'flagged')
        self.evidence['facts'] = 'A' * 800 + '.'
        self.draft['applications']['notice_and_cure']['evidence_ids'] = ['facts_1']
        self.assertEqual(self.check()[1]['evidence_check'], 'flagged')

    def test_invalid_wrong_role_or_duplicate_observations_are_not_fabricated(self):
        for observations in [[{'scope': 'case_fact', 'evidence_id': 'contract_2'}],
                             [{'scope': 'contract_term', 'evidence_id': 'missing'}],
                             [self.draft['observations'][0], self.draft['observations'][0]]]:
            with self.subTest(observations=observations):
                self.draft['observations'] = observations
                with self.assertRaises(HTTPException) as caught:
                    self.check()
                self.assertEqual(caught.exception.status_code, 502)

    def test_units_cover_normalized_inputs_and_preserve_unicode_offsets(self):
        self.evidence['facts'] = 'Cafe\u0301 \U0001f4c4: notice dated 10\u202fAugust, receipt disputed. A loss of GHS 2.50 is alleged.'
        catalog = evidence_units(self.evidence)
        for role, source in self.evidence.items():
            units = [u for u in catalog.values() if u['role'] == role]
            self.assertEqual(' '.join(u['text'] for u in units), normalised(source))
            for unit in units:
                self.assertEqual(normalised(source)[unit['start']:unit['end']], unit['text'])

    def test_generation_is_one_bounded_call_with_complete_units_not_duplicate_free_text(self):
        intelligence = SimpleNamespace(generate=Mock(return_value=self.draft))
        claims, evidence = generate_focused_claims(intelligence, self.evidence['facts'], self.evidence['contract'], self.evidence['authority'], source_ids=self.ids)
        self.assertEqual(intelligence.generate.call_count, 1)
        data = intelligence.generate.call_args.args[1]
        self.assertNotIn('reviewed_evidence', data)
        self.assertEqual({u['id'] for u in data['evidence_units']}, set(evidence_units(self.evidence)))
        self.assertEqual(evidence, self.evidence)
        self.assertEqual(len(claims), 4)

    def test_reverification_keeps_topics_source_wording_and_reference_failures(self):
        self.draft['applications']['notice_and_cure']['evidence_ids'] = ['missing']
        original = self.check()
        checked = copy.deepcopy(original)
        for claim in checked:
            claim.pop('application_topic', None)
            claim.pop('wording_origin', None)
            claim['check_issues'] = []
        result = restore_application_checks(checked, original)
        self.assertEqual(result[0]['wording_origin'], 'source_text')
        self.assertEqual(result[1]['application_topic'], 'notice_and_cure')
        self.assertIn('invalid_evidence_reference', result[1]['check_issues'])
        self.assertEqual(result[1]['evidence_check'], 'flagged')
        with self.assertRaises(HTTPException):
            restore_application_checks(copy.deepcopy(checked), original[:-1])

    def test_supported_application_without_fact_proof_is_withheld_by_verifier(self):
        self.draft['observations'] = []
        self.draft['applications']['notice_and_cure'].update(status='aligned_sources', evidence_ids=['contract_2', 'facts_1', 'authority_1'])
        claims = self.check()
        # Older or future affirmative applications still need fact evidence in the verifier.
        claims[0]['scope'] = 'comparison'
        def assess(*args, **kwargs):
            return {'assessments': [{'claim_id': 'C1', 'verdict': 'supported', 'reason': 'Synthetic proposed support, not a legal conclusion.',
                'evidence': [{'role': role, 'text': text} for role, text in [('contract', self.evidence['contract'].split('. ')[1] + '.'),
                                                                          ('authority', self.evidence['authority'].split('. ')[0] + '.')]]}]}
        intelligence = SimpleNamespace(generate=Mock(side_effect=assess), settings=SimpleNamespace(model='openai/gpt-oss-20b', max_input_tokens=4000))
        checked, _ = verify_claims(intelligence, claims, self.evidence, self.ids)
        self.assertEqual(checked[0]['semantic_status'], 'not_checked')
        self.assertIn('withheld', checked[0]['verification']['reason'].lower())
