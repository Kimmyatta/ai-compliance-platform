import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))

from evals.termination_evals import load_cases, probe_claim, probe_summary, rescore_report, screen_text, verifier_metrics
from legal_app.atomic_claims import check_claims, normalised


class AtomicClaimTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            'contract': 'Written notice must allow fourteen days after receipt to remedy the breach.',
            'authority': 'The court in that case examined the conditions in the express termination clause.',
            'facts': 'The parties dispute whether reasonable access was provided for remedial work.',
        }

    def check(self, scope='contract_term', text='The contract specifies fourteen days after receipt.', spans=None):
        if spans is None:
            spans = [{'role': 'contract', 'text': 'fourteen days after receipt'}]
        return check_claims({'claims': [{'scope': scope, 'text': text, 'spans': spans}]}, self.evidence,
                            {'contract': 1, 'authority': 2})[0]

    def test_matched_span_has_reproducible_offsets_and_remains_semantically_unchecked(self):
        result = self.check()
        span = result['spans'][0]
        self.assertEqual(self.evidence['contract'][span['start']:span['end']], span['text'])
        self.assertEqual(span['source_id'], 1)
        self.assertEqual(result['evidence_check'], 'matched')
        self.assertEqual(result['semantic_status'], 'not_checked')

    def test_invented_or_spliced_span_is_flagged_and_retained(self):
        result = self.check(spans=[{'role': 'contract', 'text': 'Written notice ... remedy the breach.'}])
        self.assertEqual(result['evidence_check'], 'flagged')
        self.assertIn('span_not_found', result['check_issues'])
        self.assertIsNone(result['spans'][0]['end'])
        self.assertIn('...', result['spans'][0]['text'])

    def test_role_is_checked_even_when_the_words_occur_in_a_different_role(self):
        result = self.check(scope='general_principle')
        self.assertIn('missing_required_role', result['check_issues'])
        self.assertIn('wrong_evidence_role', result['check_issues'])

    def test_comparison_requires_contract_and_authority_spans(self):
        result = self.check(scope='comparison')
        self.assertIn('missing_required_role', result['check_issues'])
        result = self.check(scope='comparison', spans=[{'role': role, 'text': self.evidence[role]} for role in ('contract', 'authority')])
        self.assertEqual(result['evidence_check'], 'matched')

    def test_unresolved_point_can_have_no_establishing_span(self):
        self.assertEqual(self.check(scope='not_established', spans=[])['evidence_check'], 'no_evidence')
        self.assertEqual(self.check(spans=[])['evidence_check'], 'flagged')

    def test_current_case_facts_cannot_be_supported_by_judgment_facts(self):
        result = self.check(scope='case_fact', spans=[{'role': 'authority', 'text': self.evidence['authority']}])
        self.assertIn('wrong_evidence_role', result['check_issues'])

    def test_fact_span_has_no_invented_document_id(self):
        result = self.check(scope='case_fact', spans=[{'role': 'facts', 'text': self.evidence['facts']}])
        self.assertEqual(result['evidence_check'], 'matched')
        self.assertIsNone(result['spans'][0]['source_id'])

    def test_unicode_and_pdf_whitespace_normalisation_preserve_highlight_boundaries(self):
        self.evidence['contract'] = '\U0001f4c4 Cafe\u0301 agreement:\n fourteen days after receipt.'
        result = self.check()
        span = result['spans'][0]
        canonical = normalised(self.evidence['contract'])
        self.assertEqual(canonical[span['start']:span['end']], 'fourteen days after receipt')
        self.assertGreater(span['start'], 0)

    def test_an_unsupported_inference_can_still_match_text_and_is_never_labelled_supported(self):
        result = self.check(text='The contract is therefore legally enforceable.')
        self.assertEqual(result['evidence_check'], 'matched')
        self.assertEqual(result['semantic_status'], 'not_checked')
        self.assertNotIn('supported', result.values())


class EvaluationFixtureTests(unittest.TestCase):
    def test_twelve_unique_fixtures_have_separate_development_and_holdout_groups(self):
        cases = load_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({case['id'] for case in cases}), 12)
        self.assertEqual(sum(case['split'] == 'development' for case in cases), 8)
        self.assertEqual(sum(case['split'] == 'holdout' for case in cases), 4)

    def test_every_fixture_has_supported_and_unsupported_probe_annotations(self):
        for case in load_cases():
            with self.subTest(case=case['id']):
                self.assertIn('supported', {p['label'] for p in case['probes']})
                self.assertTrue(any(p['label'] != 'supported' for p in case['probes']))
                for probe in case['probes']:
                    self.assertTrue(probe_claim(case, probe)['spans'])

    def test_probe_baseline_exposes_the_limit_of_text_matching(self):
        summary = probe_summary(load_cases())
        self.assertEqual(summary['probe_count'], 24)
        self.assertEqual(summary['unsupported_probes_with_matched_spans'], 12)
        self.assertTrue(all(r['semantic_status'] == 'not_checked' for r in summary['records']))

    def test_screens_report_patterns_without_claiming_semantic_accuracy(self):
        case = load_cases()[0]
        screen = screen_text(case, 'There is no termination clause. The cure period starts on dispatch.')
        self.assertIn('no-clause', screen['forbidden_pattern_flags'])
        self.assertIn('receipt-not-dispatch', screen['missing_required_patterns'])
        self.assertEqual(screen['semantic_assessment'], 'not_performed')
        self.assertIn('Lexical screening only', screen['warning'])

    def test_typographic_hyphen_and_adjectival_day_do_not_create_false_omissions(self):
        case = load_cases()[1]
        for text in ('The contract specifies seven days.', 'The contract specifies a seven-day period.',
                     'The contract specifies a seven\u2011day period.'):
            self.assertEqual(screen_text(case, text)['missing_required_patterns'], [])
        self.assertIn('invented-fourteen', screen_text(case, 'The period is fourteen\u2011day.')['forbidden_pattern_flags'])

    def test_offline_rescoring_preserves_original_run_and_does_not_assert_semantic_support(self):
        case = load_cases()[1]
        report = {'workflow': 'legacy', 'fixture_sha256': 'old-fixture', 'results': [{
            'case': case['id'], 'generation_status': 'completed',
            'output': {'similarities': '', 'differences': 'The contract specifies a seven\u2011day period.',
                       'supporting_argument': '', 'adverse_argument': '', 'unanswered_questions': []},
            'screen': {'missing_required_patterns': ['seven-days']},
        }]}
        rescored = rescore_report(report, load_cases())
        self.assertEqual(report['results'][0]['screen']['missing_required_patterns'], ['seven-days'])
        self.assertEqual(rescored['results'][0]['screen']['missing_required_patterns'], [])
        self.assertEqual(rescored['previous_fixture_sha256'], 'old-fixture')
        self.assertEqual(rescored['results'][0]['screen']['semantic_assessment'], 'not_performed')

    def test_verifier_metrics_separate_false_acceptance_from_unchecked_probes(self):
        def probe(expected, actual, origin='model'):
            return {'expected': expected, 'actual': actual, 'assessment': {'origin': origin}}
        metrics = verifier_metrics([{'verifier_probes': [probe('supported', 'supported'),
            probe('contradicted', 'supported'), probe('insufficient_evidence', 'not_checked', 'not_checked'),
            probe('supported', 'insufficient_evidence')]}])
        self.assertEqual(metrics['annotated_probes'], 4)
        self.assertEqual(metrics['model_assessed'], 3)
        self.assertEqual(metrics['unchecked'], 1)
        self.assertEqual(metrics['coverage'], .75)
        self.assertEqual(metrics['unsupported_claims_accepted'], 1)
        self.assertEqual(metrics['false_acceptance_rate_on_assessed_negatives'], 1)
        self.assertEqual(metrics['supported_claims_flagged_or_abstained'], 1)

    def test_verifier_results_cannot_be_lexically_rescored(self):
        with self.assertRaises(ValueError):
            rescore_report({'workflow': 'verifier', 'results': []}, load_cases())

    def test_policy_gate_does_not_hide_a_raw_model_false_acceptance(self):
        metrics = verifier_metrics([{'verifier_probes': [{'expected': 'insufficient_evidence', 'actual': 'not_checked',
            'assessment': {'origin': 'policy_gate', 'model_verdict': 'supported'}}]}])
        self.assertEqual(metrics['model_assessed'], 1)
        self.assertEqual(metrics['unsupported_claims_accepted'], 1)
        self.assertEqual(metrics['pipeline_unsupported_claims_accepted'], 0)
        self.assertEqual(metrics['model_support_withheld_by_policy'], 1)


if __name__ == '__main__':
    unittest.main()
