import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from fastapi import HTTPException
from groq import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from legal_app.config import Settings
from legal_app.intelligence import Intelligence, SYSTEM
from legal_app.request_budget import input_tokens, messages_for, response_format_for
from legal_app.schemas import CaseAnalysisReport, CaseBrief, CaseFinding, GeneratedReport


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(Path('.'), 'test-key', 'openai/gpt-oss-20b', [])
        self.intelligence = Intelligence(self.settings)
        self.sources = [
            {'chunk_id': i + 1, 'document_id': f'doc-{i // 10}',
             'title': f'Synthetic judgment {i // 10}', 'locator': f'Page {i + 1}',
             'court': 'Synthetic court', 'citation': 'TEST ONLY', 'kind': 'judgment',
             'text': 'Synthetic contract paragraph. ' * 150,
             'filename': 'not-needed-in-prompt.pdf', 'source_url': 'https://example.test/authority'}
            for i in range(30)
        ]

    def provider_error(self, status, headers=None, code=None):
        return APIStatusError('PRIVATE_PROMPT_DO_NOT_EXPOSE',
            response=httpx.Response(status, headers=headers,
                request=httpx.Request('POST', 'https://api.groq.com/test')),
            body={'error': {'message': 'PRIVATE_PROMPT_DO_NOT_EXPOSE', 'code': code}})

    def failing_call(self, error):
        with patch('groq.Groq') as client:
            client.return_value.__enter__.return_value.chat.completions.create.side_effect = error
            with self.assertRaises(HTTPException) as caught:
                self.intelligence.generate('Extract a brief.', {}, CaseBrief)
        return caught.exception

    def test_report_fits_budget_preserves_whole_passages_and_document_diversity(self):
        self.intelligence.generate = Mock(return_value={
            'title': 'Synthetic report', 'findings': [{'category': 'comparison', 'text': 'Synthetic finding', 'source_ids': [1], 'supporting_quotes': [{'source_id': 1, 'quote': 'Synthetic contract paragraph.'}]}],
            'limitations': ['Synthetic test only'],
        })
        report = self.intelligence.report('Contract termination', self.sources, 'Confirmed synthetic facts.')
        task, data, schema = self.intelligence.generate.call_args.args
        count = input_tokens(messages_for(SYSTEM, task, data, schema, self.settings.model), self.settings.model, schema)
        self.assertLessEqual(count, self.settings.max_input_tokens)
        self.assertLess(count + self.settings.max_completion_tokens, 8000)
        self.assertLess(len(report['sources']), len(self.sources))
        self.assertEqual({s['document_id'] for s in report['sources']}, {'doc-0', 'doc-1', 'doc-2'})
        for source in report['sources']:
            self.assertEqual(source, self.sources[source['chunk_id'] - 1])
        self.assertTrue(any('input budget' in note.lower() for note in report['limitations']))

    def test_omitted_source_cannot_be_cited(self):
        self.intelligence.generate = Mock(return_value={
            'title': 'Bad report', 'findings': [{'category': 'comparison', 'text': 'Unsupported', 'source_ids': [30]}],
            'limitations': [],
        })
        with self.assertRaises(HTTPException) as caught:
            self.intelligence.report('Contract termination', self.sources, 'Confirmed synthetic facts.')
        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn(30, [s['chunk_id'] for s in self.intelligence.generate.call_args.args[1]['authority_passages']])

    def test_case_evidence_and_authorities_have_separate_roles_within_one_budget(self):
        case = {**self.sources[0], 'chunk_id': 1001, 'document_id': 'private-case',
                'kind': 'matter', 'title': 'Fictional contract file', 'citation': '',
                'text': 'The fictional agreement requires signed acceptance before final payment. ' * 12}
        self.intelligence.generate = Mock(return_value={
            'title': 'Comparison', 'findings': [{'category': 'comparison', 'text': 'A qualified comparison.', 'source_ids': [1, 1001], 'supporting_quotes': [{'source_id': 1, 'quote': 'Synthetic contract paragraph.'}]}],
            'limitations': [],
        })
        facts = 'Lawyer-confirmed facts (source_ids: 1001).'
        report = self.intelligence.report('Whether final payment is due', self.sources, facts, case_sources=[case])
        task, data, schema = self.intelligence.generate.call_args.args
        self.assertEqual(data['confirmed_case_facts'], facts)
        self.assertEqual(data['confirmed_issues'], 'Whether final payment is due')
        self.assertEqual(data['case_passages'], [case])
        self.assertTrue(all(s['kind'] == 'judgment' for s in data['authority_passages']))
        self.assertNotIn('sources', data)
        self.assertLessEqual(input_tokens(messages_for(SYSTEM, task, data, schema, self.settings.model), self.settings.model, schema), 4000)
        self.assertIn(case, report['sources'])

    def test_a_case_document_alone_cannot_support_a_legal_comparison(self):
        case = {**self.sources[0], 'chunk_id': 1001, 'kind': 'matter', 'text': 'Synthetic contract terms.'}
        self.intelligence.generate = Mock(return_value={
            'title': 'Bad comparison', 'findings': [{'category': 'comparison', 'text': 'Unsupported law.', 'source_ids': [1001]}],
            'limitations': [],
        })
        with self.assertRaises(HTTPException) as caught:
            self.intelligence.report('Contract', self.sources[:1], 'Confirmed facts.', case_sources=[case])
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn('legal authority', caught.exception.detail)

    def test_gap_only_response_is_not_saved_as_a_successful_comparison(self):
        self.intelligence.generate = Mock(return_value={
            'title': 'No comparison', 'findings': [{'category': 'evidence_gap', 'text': 'Missing facts.', 'source_ids': [1]}],
            'limitations': [],
        })
        with self.assertRaises(HTTPException) as caught:
            self.intelligence.report('Contract', self.sources[:1], 'Confirmed facts.')
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn('supported comparison', caught.exception.detail)

    def test_uncited_evidence_gap_is_valid_but_uncited_legal_claim_is_not(self):
        result = CaseAnalysisReport.model_validate({
            'title': 'Mixed report', 'findings': [
                {'category': 'comparison', 'text': 'A cited comparison.', 'source_ids': [1], 'supporting_quotes': [{'source_id': 1, 'quote': 'Synthetic contract paragraph.'}]},
                {'category': 'evidence_gap', 'text': 'No invoice supplied.', 'source_ids': []},
            ], 'limitations': ['Limited evidence'],
        })
        self.assertEqual(result.findings[1].source_ids, [])
        for category in ('comparison', 'possible_approach'):
            with self.subTest(category=category), self.assertRaises(ValidationError):
                CaseFinding.model_validate({'category': category, 'text': 'An uncited legal claim.', 'source_ids': []})

    def test_case_analysis_can_use_manual_confirmed_facts_without_uploaded_case_passages(self):
        self.intelligence.generate = Mock(return_value={
            'title': 'Manual case comparison', 'findings': [{'category': 'comparison', 'text': 'A comparison on the stated premise.', 'source_ids': [1], 'supporting_quotes': [{'source_id': 1, 'quote': 'Synthetic contract paragraph.'}]}],
            'limitations': [],
        })
        result = self.intelligence.report('Contract', self.sources[:1], 'Manually confirmed factual premise.')
        data = self.intelligence.generate.call_args.args[1]
        self.assertEqual(data['case_passages'], [])
        self.assertEqual(data['confirmed_case_facts'], 'Manually confirmed factual premise.')
        self.assertEqual(len(result['findings']), 1)

    def test_invented_supporting_quote_is_rejected(self):
        self.intelligence.generate = Mock(return_value={
            'title': 'Bad quotation', 'findings': [{'category': 'comparison', 'text': 'Unsupported rule.',
                'source_ids': [1], 'supporting_quotes': [{'source_id': 1, 'quote': 'An invented rule about contractual damages.'}]}],
            'limitations': [],
        })
        with self.assertRaises(HTTPException) as caught:
            self.intelligence.report('Contract', self.sources[:1], 'Confirmed synthetic facts.')
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn('quotation could not be verified', caught.exception.detail)

    def test_exact_quote_allows_pdf_line_breaks_but_preserves_words(self):
        source = {**self.sources[0], 'text': 'A contractual notice must identify the\n breach and allow an opportunity to remedy it.'}
        self.intelligence.generate = Mock(return_value={
            'title': 'Supported comparison', 'findings': [{'category': 'comparison', 'text': 'A limited comparison.',
                'source_ids': [1], 'supporting_quotes': [{'source_id': 1, 'quote': 'A contractual notice must identify the breach and allow an opportunity to remedy it.'}]}],
            'limitations': [],
        })
        result = self.intelligence.report('Contract notice', [source], 'Confirmed synthetic facts.')
        self.assertEqual(result['grounding_version'], 1)

    def test_case_only_quote_cannot_support_legal_comparison(self):
        case = {**self.sources[0], 'kind': 'matter', 'document_id': 'private-case', 'chunk_id': 1001,
                'text': 'Synthetic private contract terms.'}
        self.intelligence.generate = Mock(return_value={
            'title': 'Case is not law', 'findings': [{'category': 'comparison', 'text': 'Unsupported law.',
                'source_ids': [1, 1001], 'supporting_quotes': [{'source_id': 1001, 'quote': case['text']}]}],
            'limitations': [],
        })
        with self.assertRaises(HTTPException) as caught:
            self.intelligence.report('Contract', self.sources[:1], 'Confirmed synthetic facts.', case_sources=[case])
        self.assertIn('verifiable authority quotation', caught.exception.detail)

    def test_oversized_confirmed_facts_are_rejected_without_clipping(self):
        facts = 'Confirmed synthetic contract facts. ' * 5000
        self.intelligence.generate = Mock()
        with self.assertRaises(HTTPException) as caught:
            self.intelligence.report('Contract termination', self.sources, facts)
        self.assertEqual(caught.exception.status_code, 413)
        self.assertIn('never silently truncated', caught.exception.detail)
        self.intelligence.generate.assert_not_called()

    def test_brief_reports_actual_sources_and_incomplete_coverage(self):
        self.intelligence.settings = replace(self.settings, max_input_tokens=1800)
        self.sources = [{**s, 'text': (f"Source {i} records a disputed notice event with a separately identified date and documentary limitation. " * 30)}
                        for i, s in enumerate(self.sources)]
        self.intelligence.generate = Mock(side_effect=lambda task, data, schema, **kw: {
            'evidence_ids': [data['case_units'][0]['id']], 'issues': ['Contract'], 'missing_information': [],
        })
        result = self.intelligence.brief(self.sources, False)
        self.assertTrue(result['truncated'])
        self.assertLess(len(result['sources']), len(self.sources))
        sent_ids = {unit['source_id'] for unit in self.intelligence.generate.call_args.args[1]['case_units']}
        self.assertEqual({source['chunk_id'] for source in result['sources']}, sent_ids)
        self.assertEqual(result['facts'], result['fact_excerpts'][0]['text'])

    def test_prompt_drops_unnecessary_metadata_but_keeps_exact_text(self):
        messages = messages_for(SYSTEM, 'Research', {'sources': self.sources[:1]}, GeneratedReport)
        source = json.loads(messages[1]['content'])['input']['sources'][0]
        self.assertNotIn('filename', source)
        self.assertNotIn('source_url', source)
        self.assertEqual(source['text'], self.sources[0]['text'])
        self.assertEqual(source['chunk_id'], 1)

    def test_strict_schema_requires_nested_fields_without_mutating_local_schema(self):
        original = CaseAnalysisReport.model_json_schema()
        response_format = response_format_for(CaseAnalysisReport, self.settings.model)
        self.assertTrue(response_format['json_schema']['strict'])
        definition = response_format['json_schema']['schema']
        for node in [definition, *definition['$defs'].values()]:
            self.assertFalse(node['additionalProperties'])
            self.assertEqual(set(node['required']), set(node['properties']))
        self.assertEqual(CaseAnalysisReport.model_json_schema(), original)
        self.assertEqual(response_format_for(CaseBrief, 'other-model'), {'type': 'json_object'})
        messages = messages_for(SYSTEM, 'Research', {}, CaseAnalysisReport, self.settings.model)
        self.assertNotIn('required_schema', json.loads(messages[1]['content']))

    def test_rate_limit_preserves_retry_after_and_does_not_expose_provider_body(self):
        with self.assertLogs('legal_app.intelligence', level='WARNING') as logs:
            error = self.failing_call(self.provider_error(429, {'Retry-After': '6.2'}))
        self.assertEqual(error.status_code, 429)
        self.assertEqual(error.headers['Retry-After'], '7')
        self.assertIn('Wait 7 seconds', error.detail)
        self.assertNotIn('PRIVATE_PROMPT', error.detail + ''.join(logs.output))
        self.assertNotIn(self.settings.api_key, error.detail + ''.join(logs.output))

    def test_provider_size_error_is_not_reported_as_bad_key(self):
        error = self.failing_call(self.provider_error(413))
        self.assertEqual(error.status_code, 413)
        self.assertIn('too large', error.detail)
        self.assertNotIn('API key', error.detail)

    def test_shared_cooldown_blocks_other_model_tasks_without_provider_calls(self):
        with patch('legal_app.intelligence.time.monotonic', return_value=100):
            self.failing_call(self.provider_error(429, {'Retry-After': '6'}))
        with patch('legal_app.intelligence.time.monotonic', return_value=103), patch('groq.Groq') as client:
            with self.assertRaises(HTTPException) as caught:
                self.intelligence.generate('Another task', {}, CaseBrief)
            self.assertEqual(caught.exception.status_code, 429)
            self.assertEqual(caught.exception.headers['Retry-After'], '4')
            client.assert_not_called()
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps({
            'facts': 'Synthetic proposed facts.', 'issues': ['Termination'], 'missing_information': [],
        })))])
        with patch('legal_app.intelligence.time.monotonic', return_value=108), patch('groq.Groq') as client:
            client.return_value.__enter__.return_value.chat.completions.create.return_value = response
            self.assertEqual(self.intelligence.generate('Another task', {}, CaseBrief)['issues'], ['Termination'])

    def test_structured_generation_failure_retries_once_without_weakening_schema(self):
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps({
            'facts': 'Synthetic proposed facts.', 'issues': ['Termination'], 'missing_information': [],
        })))])
        with patch('groq.Groq') as client:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.side_effect = [self.provider_error(400, code='json_validate_failed'), response]
            result = self.intelligence.generate('Extract a brief', {}, CaseBrief)
        self.assertEqual(result['issues'], ['Termination'])
        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args_list[0], create.call_args_list[1])
        self.assertTrue(create.call_args.kwargs['response_format']['json_schema']['strict'])

    def test_repeated_format_failure_stops_after_two_calls_and_redacts_provider_body(self):
        with patch('groq.Groq') as client, self.assertLogs('legal_app.intelligence', level='WARNING') as logs:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.side_effect = self.provider_error(400, code='structured_generation_failed')
            with self.assertRaises(HTTPException) as caught:
                self.intelligence.generate('Extract a brief', {}, CaseBrief)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn('after one retry', caught.exception.detail)
        self.assertNotIn('PRIVATE_PROMPT', caught.exception.detail + ''.join(logs.output))

    def test_unknown_bad_request_is_not_retried_or_blames_issue_length(self):
        with patch('groq.Groq') as client:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.side_effect = self.provider_error(400, code='invalid_request_error')
            with self.assertRaises(HTTPException) as caught:
                self.intelligence.generate('Extract a brief', {}, CaseBrief)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn('HTTP 400', caught.exception.detail)
        self.assertNotIn('fewer legal issues', caught.exception.detail)

    def test_rate_limit_after_format_retry_stops_immediately_with_retry_after(self):
        with patch('groq.Groq') as client:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.side_effect = [self.provider_error(400, code='json_validate_failed'), self.provider_error(429, {'Retry-After': '12'})]
            with self.assertRaises(HTTPException) as caught:
                self.intelligence.generate('Extract a brief', {}, CaseBrief)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.headers['Retry-After'], '13')

    def test_authentication_model_access_and_network_errors_are_distinct(self):
        expected = [(401, 'API key'), (403, 'model'), (404, 'model')]
        for status, text in expected:
            with self.subTest(status=status):
                error = self.failing_call(self.provider_error(status))
                self.assertEqual(error.status_code, 503)
                self.assertIn(text, error.detail)
        error = self.failing_call(APIConnectionError(request=httpx.Request('POST', 'https://api.groq.com/test')))
        self.assertEqual(error.status_code, 503)
        self.assertIn('internet connection', error.detail)
        error = self.failing_call(APITimeoutError(request=httpx.Request('POST', 'https://api.groq.com/test')))
        self.assertEqual(error.status_code, 504)

    def test_generation_limits_and_output_truncation(self):
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='length', message=SimpleNamespace(content='{}'))])
        with patch('groq.Groq') as client:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.return_value = response
            with self.assertRaises(HTTPException) as caught:
                self.intelligence.generate('Extract a brief', {}, CaseBrief)
        self.assertIn('response-length limit', caught.exception.detail)
        self.assertEqual(create.call_args.kwargs['max_completion_tokens'], 3000)
        self.assertEqual(create.call_args.kwargs['reasoning_effort'], 'low')
        self.assertEqual(create.call_args.kwargs['response_format']['type'], 'json_schema')
        self.assertEqual(client.call_args.kwargs['max_retries'], 0)

    def test_single_request_over_budget_never_calls_provider(self):
        intelligence = Intelligence(replace(self.settings, max_input_tokens=10))
        with patch('groq.Groq') as client:
            with self.assertRaises(HTTPException) as caught:
                intelligence.generate('Brief', {}, CaseBrief)
        self.assertEqual(caught.exception.status_code, 413)
        client.assert_not_called()

    def test_generation_uses_the_supplied_task_specific_system_prompt(self):
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps({
            'facts': 'Synthetic proposed facts.', 'issues': ['Termination'], 'missing_information': [],
        })))])
        with patch('groq.Groq') as client:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.return_value = response
            self.intelligence.generate('Extract', {}, CaseBrief, system='Task-specific evidence instructions.')
        self.assertEqual(create.call_args.kwargs['messages'][0]['content'], 'Task-specific evidence instructions.')

    def test_verifier_completion_budget_cannot_exceed_the_configured_limit(self):
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps({
            'facts': 'Synthetic proposed facts.', 'issues': ['Termination'], 'missing_information': [],
        })))])
        intelligence = Intelligence(replace(self.settings, max_completion_tokens=500))
        with patch('groq.Groq') as client:
            create = client.return_value.__enter__.return_value.chat.completions.create
            create.return_value = response
            intelligence.generate('Extract', {}, CaseBrief, completion_tokens=1800)
        self.assertEqual(create.call_args.kwargs['max_completion_tokens'], 500)


if __name__ == '__main__':
    unittest.main()
