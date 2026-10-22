import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from legal_app.case_evidence import (attach_document_sources, documentary_facts, extractive_brief,
                                     source_units, validate_saved_basis, BRIEF_TASK)
from legal_app.atomic_claims import normalised
from legal_app.documents import extract_units, split_units
from legal_app.focused_claims import TOPICS
from legal_app.intelligence import SYSTEM as BRIEF_SYSTEM
from legal_app.main import create_app
from legal_app.request_budget import input_tokens, messages_for
from legal_app.schemas import ExtractiveCaseBrief, FocusedTerminationDraft


CASE = ("ECS questions the logger calibration and says power interruptions caused the excursions. "
        "Neither party has produced an acceptance certificate signed by EHL.\n\n"
        "A courier record shows delivery at ECS's office on 12 August. ECS acknowledges office receipt. "
        "ECS proposed a repair visit for 20 August at 10 a.m. "
        "EHL says access during medicine handling was unsafe and offered entry after 5 p.m. that day or on 24 August. "
        "The available email chain does not establish whether either alternative was finally agreed.")
CONTRACT = 'Written notice must allow fourteen days after receipt to remedy a material breach. The customer shall provide reasonable access for remedial work.'
AUTHORITY = 'In general, a termination clause sets the conditions for ending the agreement.'
WRONG_SUMMARY = 'EHL admits power interruptions caused all defects. No acceptance certificate was signed. Access was refused.'


class CaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name))
        self.client = TestClient(self.app)
        self.store = self.app.state.store
        self.matter = self.client.post('/api/matters', json={'name': 'Source-grounding regression'}).json()['id']
        self.other = self.client.post('/api/matters', json={'name': 'Unrelated private case'}).json()['id']
        self.case = self.upload(CASE, 'matter', self.matter)
        self.contract = self.upload(CONTRACT, 'matter', self.matter)
        self.authority = self.upload(AUTHORITY, 'judgment')
        self.upload('A courier receipt in another private case states 99 December. Repair access was refused.', 'matter', self.other)
        self.ai = self.app.state.intelligence

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self, text, kind, matter=''):
        response = self.client.post('/api/documents', data={'kind': kind, 'matter_id': matter,
            'permission_confirmed': 'true'}, files={'file': ('regression.txt', text.encode(), 'text/plain')})
        self.assertEqual(response.status_code, 200, response.text)
        with self.store.connect() as db:
            source_id = db.execute('SELECT id FROM chunks WHERE document_id=? ORDER BY id', (response.json()['id'],)).fetchone()['id']
        return self.store.source(source_id)

    def test_receipt_access_attribution_and_document_limitations_survive_selection(self):
        basis = documentary_facts(self.store, self.matter)
        self.assertIn("delivery at ECS's office on 12 August", basis['text'])
        self.assertIn('ECS proposed a repair visit for 20 August', basis['text'])
        self.assertIn('offered entry after 5 p.m.', basis['text'])
        self.assertIn('whether either alternative was finally agreed', basis['text'])
        self.assertIn('ECS questions the logger calibration', basis['text'])
        self.assertIn('Neither party has produced', basis['text'])
        self.assertNotIn('99 December', basis['text'])
        self.assertTrue(all(s['kind'] == 'matter' for s in basis['sources']))
        for topic in TOPICS:
            self.assertTrue(basis['topics'][topic])
        validate_saved_basis(self.store, self.matter, basis)

    def test_bounded_selection_discloses_omissions_and_preserves_whole_units(self):
        self.upload(' '.join(f'Notice {i} was received with a long disputed explanation about repair access and material breach.'
                             for i in range(150)), 'matter', self.matter)
        basis = documentary_facts(self.store, self.matter)
        self.assertLessEqual(len(basis['text']), 4500)
        self.assertTrue(basis['coverage']['incomplete'])
        validate_saved_basis(self.store, self.matter, basis)

    def test_overlapping_page_fragments_do_not_replace_available_complete_excerpts(self):
        fragments = [
            {'chunk_id': 1, 'document_id': 'page-overlap', 'locator': 'Page 3',
             'text': "A courier record shows delivery on 12 August. ECS disputes whether the notice supplied enough technical detail, but acknowledges office r"},
            {'chunk_id': 2, 'document_id': 'page-overlap', 'locator': 'Page 3',
             'text': "delivery on 12 August. ECS disputes whether the notice supplied enough technical detail, but acknowledges office receipt. ECS proposed a repair visit at 10 a.m. EHL offered access after 5 p.m. that day or on 24 August."},
        ]
        units = source_units(fragments)
        joined = ' '.join(u['text'] for u in units)
        self.assertNotIn('office r ECS', joined)
        self.assertIn('acknowledges office receipt.', joined)
        self.assertTrue(any('after 5 p.m. that day or on 24 August.' in u['text'] for u in units))
        self.assertFalse(any(u['text'] == 'delivery on 12 August.' for u in units))

    def test_saved_topic_references_and_offsets_are_validated(self):
        basis = documentary_facts(self.store, self.matter)
        for change in ('topic', 'offset'):
            broken = copy.deepcopy(basis)
            if change == 'topic':
                broken['topics']['remedial_access'] = ['invented-reference']
            else:
                broken['units'][0]['corpus_start'] = 1
            with self.assertRaises(HTTPException) as caught:
                validate_saved_basis(self.store, self.matter, broken)
            self.assertEqual(caught.exception.status_code, 409)

    def make_report(self):
        def generate(task, data, schema, **kwargs):
            if schema is FocusedTerminationDraft:
                facts = [u for u in data['evidence_units'] if u['role'] == 'facts']
                self.assertNotIn(WRONG_SUMMARY, str(data))
                self.assertNotIn('No acceptance certificate was signed', str(data))
                unit = next(u for u in facts if 'ECS questions the logger' in u['text'])
                return {'observations': [{'scope': 'case_fact', 'evidence_id': unit['id']}],
                        'applications': {topic: {'status': 'evidence_gap', 'evidence_ids': [], 'question': question}
                            for topic, question in zip(TOPICS, ['confirm_notice_receipt', 'resolve_remedial_access', 'identify_materiality_test'])}}
            claim = data['claims'][0]
            return {'assessments': [{'claim_id': claim['claim_id'], 'verdict': 'supported',
                    'reason': 'This copies the documentary attribution, not proof that the explanation is true.',
                    'evidence': claim['selected_spans']}]}
        self.ai.generate = Mock(side_effect=generate)
        response = self.client.post('/api/case-analysis/termination', json={'matter_id': self.matter,
            'facts': WRONG_SUMMARY, 'confirmed': True, 'reasoning_confirmed': True,
            'contract': {'source_id': self.contract['chunk_id'], 'quote': CONTRACT},
            'authority': {'source_id': self.authority['chunk_id'], 'quote': AUTHORITY}})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_new_report_never_verifies_the_incorrect_entered_summary_against_itself(self):
        report = self.make_report()
        payload = report['payload']
        self.assertEqual(payload['confirmed_facts'], WRONG_SUMMARY)
        self.assertNotIn('No acceptance certificate was signed', payload['evidence_texts']['facts'])
        claim = payload['claims'][0]
        self.assertEqual(claim['factual_origin'], 'case_document')
        self.assertIn('ECS questions', claim['text'])
        self.assertEqual(claim['spans'][0]['source_id'], self.case['chunk_id'])
        self.assertEqual(claim['verification']['evidence'][0]['source_id'], self.case['chunk_id'])
        self.assertEqual(claim['semantic_status'], 'supported')
        self.assertTrue(payload['case_evidence']['topics']['remedial_access'])
        self.assertEqual(payload['verification']['model_assessed'], 1)

    def test_documentary_verification_uses_the_saved_basis_and_leaves_history_unchanged(self):
        report = self.make_report()
        saved = copy.deepcopy(report['payload'])
        self.ai.generate.reset_mock()
        response = self.client.post(f"/api/reports/{report['id']}/verify", json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.ai.generate.call_count, 1)
        self.assertEqual(response.json()['payload']['case_evidence'], saved['case_evidence'])
        self.assertIn('ECS questions', response.json()['payload']['claims'][0]['text'])
        self.assertEqual(self.store.report(report['id'])['payload'], saved)

    def test_changed_or_cross_matter_saved_evidence_rejects_before_model_call(self):
        report = self.make_report()
        for cross_matter in (False, True):
            payload = copy.deepcopy(report['payload'])
            if cross_matter:
                private = self.store.matter_passages(self.other)[0][0]
                payload['case_evidence']['sources'] = [private]
            else:
                payload['case_evidence']['sources'][0]['text'] += ' Changed text.'
            bad = self.store.save_report('case_analysis', self.matter, 'Tampered evidence fixture', payload)
            self.ai.generate.reset_mock()
            result = self.client.post(f"/api/reports/{bad['id']}/verify", json={})
            self.assertIn(result.status_code, (409, 422), result.text)
            self.ai.generate.assert_not_called()

    def test_temperature_evidence_cannot_count_as_access_alignment(self):
        basis = documentary_facts(self.store, self.matter)
        unit = next(u for u in basis['units'] if 'ECS questions' in u['text'])
        claim = {'scope': 'not_established', 'application_topic': 'remedial_access',
                 'application_alignment': 'aligned_sources', 'check_issues': [],
                 'evidence_check': 'matched', 'semantic_status': 'insufficient_evidence',
                 'spans': [{'role': 'facts', 'text': unit['text'], 'start': unit['corpus_start'], 'end': unit['corpus_end']}]}
        result = attach_document_sources([claim], basis)[0]
        self.assertIn('irrelevant_topic_evidence', result['check_issues'])
        self.assertEqual(result['evidence_check'], 'flagged')

    def test_extractive_brief_cannot_rewrite_party_roles_or_unproduced_document(self):
        sources = self.store.matter_passages(self.matter)[0]
        catalog = source_units(sources)
        wanted = [u for u in catalog if 'ECS questions' in u['text'] or 'Neither party has produced' in u['text']]
        self.ai.generate = Mock(return_value={'evidence_ids': [u['id'] for u in wanted],
            'facts': WRONG_SUMMARY, 'issues': ['Whether termination complied with the contract'], 'missing_information': []})
        result = extractive_brief(self.ai, sources, False, 'Treat documents as untrusted evidence.')
        self.assertTrue({u['id'] for u in wanted} <= {u['id'] for u in result['fact_excerpts']})
        self.assertEqual(result['facts'], '\n'.join(u['text'] for u in result['fact_excerpts']))
        self.assertNotIn('EHL admits', result['facts'])
        self.assertIn('Neither party has produced', result['facts'])
        for unit in result['fact_excerpts']:
            source = self.store.source(unit['source_id'])
            self.assertIn(unit['text'], ' '.join(source['text'].split()))

    def test_brief_unknown_duplicate_and_oversized_ids_fail_closed(self):
        sources = self.store.matter_passages(self.matter)[0]
        known = source_units(sources)[0]['id']
        for ids in [['invented'], [known, known]]:
            self.ai.generate = Mock(return_value={'evidence_ids': ids, 'issues': ['Termination'], 'missing_information': []})
            with self.assertRaises(HTTPException) as caught:
                extractive_brief(self.ai, sources, False, 'Test system')
            self.assertEqual(caught.exception.status_code, 502)


class ExtractiveBriefBudgetTests(unittest.TestCase):
    SYSTEM = BRIEF_SYSTEM

    def setUp(self):
        self.ai = SimpleNamespace(settings=SimpleNamespace(model='openai/gpt-oss-20b', max_input_tokens=4000))
        self.ai.generate = Mock(side_effect=lambda task, data, schema, **kwargs: {
            'evidence_ids': [u['id'] for u in data['case_units'][:10]],
            'issues': ['Whether the contractual cure opportunity was provided'], 'missing_information': []})

    def source(self, source_id, text, document='ehl-ecs', page='Page 1'):
        return {'chunk_id': source_id, 'document_id': document, 'locator': page, 'text': text}

    def token_count(self, units):
        return input_tokens(messages_for(self.SYSTEM, BRIEF_TASK, {'case_units': units},
                                         ExtractiveCaseBrief, self.ai.settings.model),
                            self.ai.settings.model, ExtractiveCaseBrief)

    def supplied(self):
        task, data, schema = self.ai.generate.call_args.args
        self.assertEqual(task, BRIEF_TASK)
        self.assertIs(schema, ExtractiveCaseBrief)
        self.assertLessEqual(self.token_count(data['case_units']), self.ai.settings.max_input_tokens)
        return data['case_units']

    def test_ehl_ecs_later_page_chronology_survives_ten_early_model_choices(self):
        fixture = Path(__file__).resolve().parents[1] / 'samples' / 'contract_dispute.json'
        data = json.loads(fixture.read_text(encoding='utf-8'))
        sources = [self.source(index, ' '.join(p for section in page['sections'] for p in section['paragraphs']),
                               page=f'Page {index}') for index, page in enumerate(data['pages'], 1)]
        self.assertGreater(self.token_count(source_units(sources)), 4000)
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        supplied = self.supplied()
        model_choices = supplied[:10]
        self.assertEqual(len(model_choices), 10)
        self.assertTrue(all(u['source_id'] < 3 for u in model_choices))
        for text in ("delivery at ECS's office on 12 August", '20 August at 10 a.m.',
                     'offered entry after 5 p.m. that day or on 24 August',
                     'ECS says it could not provide an evening visit',
                     'whether either alternative was finally agreed', 'acknowledges office receipt'):
            self.assertIn(text, ' '.join(u['text'] for u in supplied))
            self.assertIn(text, result['facts'])
        self.assertEqual({u['source_id'] for u in supplied}, {1, 2, 3, 4})
        self.assertGreater(len(result['fact_excerpts']), 10)
        self.assertGreater(result['coverage']['chronology_units_retained'], 0)
        self.assertEqual(result['coverage']['input_tokens'], self.token_count(supplied))
        self.assertEqual(result['coverage']['input_budget_tokens'], 4000)
        self.assertEqual(result['coverage']['passages_considered'], 4)
        self.assertEqual(result['coverage']['passages_supplied'], 4)
        self.assertFalse(result['coverage']['source_passages_truncated'])
        self.assertTrue(result['coverage']['incomplete'])
        self.assertTrue(result['truncated'])
        self.assertEqual(result['facts'], '\n'.join(u['text'] for u in result['fact_excerpts']))
        by_id = {s['chunk_id']: s for s in sources}
        catalog = {u['id']: u for u in source_units(sources)}
        for unit in [*supplied, *result['fact_excerpts']]:
            self.assertEqual(unit, catalog[unit['id']])
            self.assertEqual(normalised(by_id[unit['source_id']]['text'])[unit['start']:unit['end']], unit['text'])

    def test_actual_ehl_ecs_pdf_chunks_preserve_later_page_dates_and_exact_offsets(self):
        fixture = Path(__file__).resolve().parents[1] / 'samples' / 'Sample_Contract_Dispute_Ghana.pdf'
        chunks = split_units(extract_units(fixture.name, fixture.read_bytes()))
        sources = [self.source(index, text, page=locator) for index, (locator, text) in enumerate(chunks, 1)]
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        supplied = self.supplied()
        for text in ("delivery at ECS's office on 12 August", '20 August at 10 a.m.',
                     'offered entry after 5 p.m. that day or on 24 August',
                     'whether either alternative was finally agreed'):
            self.assertIn(text, ' '.join(u['text'] for u in supplied))
            self.assertIn(text, result['facts'])
        by_id = {s['chunk_id']: s for s in sources}
        for unit in [*supplied, *result['fact_excerpts']]:
            self.assertEqual(normalised(by_id[unit['source_id']]['text'])[unit['start']:unit['end']], unit['text'])

    def test_issue_page_and_document_coverage_beats_a_long_first_page(self):
        sources = [self.source(1, ' '.join(f'Early background item {i} describes a separate ordinary business event.'
                                          for i in range(150))),
                   self.source(2, 'A notice identified the disputed breach.', page='Page 2'),
                   self.source(3, 'The parties disagree about remedial access.', page='Page 3'),
                   self.source(4, 'The recorded temperature excursions remain disputed.', page='Page 4'),
                   self.source(5, 'Neither party has produced a signed acceptance certificate.', document='second-file'),
                   self.source(6, 'A later independent documentary limitation is recorded.', document='second-file', page='Page 2')]
        self.ai.settings.max_input_tokens = 2200
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        supplied = self.supplied()
        self.assertEqual({u['source_id'] for u in supplied}, {1, 2, 3, 4, 5, 6})
        self.assertTrue(result['truncated'])
        self.assertEqual({s['chunk_id'] for s in result['sources']}, {u['source_id'] for u in supplied})

    def test_exact_budget_boundary_accepts_whole_unit_and_one_less_rejects(self):
        sources = [self.source(1, 'EHL alleges delayed delivery; ECS disputes responsibility.')]
        units = source_units(sources)
        self.ai.settings.max_input_tokens = self.token_count(units)
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.assertEqual(result['fact_excerpts'], units)
        self.assertFalse(result['truncated'])
        self.supplied()
        self.ai.generate.reset_mock()
        self.ai.settings.max_input_tokens -= 1
        with self.assertRaises(HTTPException) as caught:
            extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.assertEqual(caught.exception.status_code, 413)
        self.ai.generate.assert_not_called()

    def test_unavailable_and_oversized_units_never_reach_model_or_become_quotes(self):
        oversized = 'A courier record shows receipt on 12 August with ' + 'unbroken detail ' * 40 + '.'
        sources = [self.source(1, oversized), self.source(2, 'ECS disputes responsibility for defective equipment.', page='Page 2')]
        excluded_id = source_units(sources)[0]['id']
        result = extractive_brief(self.ai, sources, True, self.SYSTEM)
        self.assertEqual({u['source_id'] for u in self.supplied()}, {2})
        self.assertTrue(result['truncated'])
        self.assertTrue(result['coverage']['source_passages_truncated'])
        self.assertGreater(result['coverage']['chronology_units_omitted'], 0)
        self.assertIn('could not fit', result['warning'])
        for ids in ([excluded_id], ['unavailable-reference']):
            self.ai.generate = Mock(return_value={'evidence_ids': ids, 'issues': ['Notice'], 'missing_information': []})
            with self.assertRaises(HTTPException) as caught:
                extractive_brief(self.ai, sources, False, self.SYSTEM)
            self.assertEqual(caught.exception.status_code, 502)

    def test_available_but_token_excluded_reference_is_rejected(self):
        sources = [self.source(1, 'ECS disputes the alleged equipment defects.'),
                   self.source(2, 'A separate report contains ' + 'detailed findings ' * 15 + '.', page='Page 2')]
        first = source_units(sources[:1])
        self.ai.settings.max_input_tokens = self.token_count(first)
        excluded = source_units(sources[1:])[0]['id']
        self.ai.generate = Mock(return_value={'evidence_ids': [excluded], 'issues': ['Defects'], 'missing_information': []})
        with self.assertRaises(HTTPException) as caught:
            extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(self.supplied(), first)

    def test_whole_excerpt_character_boundary_never_clips_a_quote(self):
        complete = 'ECS reports ' + 'x' * 337 + '.'
        self.assertEqual(len(complete), 350)
        sources = [self.source(1, complete), self.source(2, complete[:-1] + 'x.', page='Page 2')]
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.assertEqual(result['facts'], complete)
        self.assertEqual({u['source_id'] for u in self.supplied()}, {1})
        self.assertTrue(result['truncated'])

    def test_priority_is_not_specific_to_ehl_ecs_or_august(self):
        sources = [self.source(1, 'A courier record shows delivery to Omega on 7 December. '
                                  'Omega acknowledges office receipt. '
                                  'Omega proposed a repair visit on 9 December. '
                                  'Delta offered entry on 11 December. '
                                  'The available email chain does not establish agreement.')]
        self.ai.generate = Mock(side_effect=lambda task, data, schema, **kwargs: {
            'evidence_ids': [data['case_units'][0]['id']], 'issues': ['Cure opportunity'], 'missing_information': []})
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.supplied()
        self.assertIn('Omega acknowledges office receipt.', result['facts'])
        self.assertIn('Omega proposed a repair visit on 9 December.', result['facts'])
        self.assertIn('Delta offered entry on 11 December.', result['facts'])
        self.assertIn('does not establish agreement.', result['facts'])

    def test_empty_oversized_only_and_prompt_over_budget_do_not_call_model(self):
        cases = [[], [self.source(1, 'X' * 351 + '.')]]
        for sources in cases:
            with self.subTest(sources=sources), self.assertRaises(HTTPException) as caught:
                extractive_brief(self.ai, sources, False, self.SYSTEM)
            self.assertEqual(caught.exception.status_code, 413)
        self.ai.settings.max_input_tokens = 1
        with self.assertRaises(HTTPException) as caught:
            extractive_brief(self.ai, [self.source(1, 'An otherwise usable complete excerpt.')], False, self.SYSTEM)
        self.assertEqual(caught.exception.status_code, 413)
        self.ai.generate.assert_not_called()

    def test_oversized_adjacent_dispute_is_not_silently_cut_from_reserved_bundle(self):
        sources = [self.source(1, 'ECS proposed a repair visit on 20 August. '
                                  + 'The alternative access arrangements remain disputed because ' + 'specific detail ' * 30 + '.'),
                   self.source(2, 'Neither party has produced a signed acceptance certificate.', document='other')]
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.assertEqual({u['source_id'] for u in self.supplied()}, {2})
        self.assertNotIn('20 August', result['facts'])
        self.assertIn('could not fit', result['warning'])

    def test_chronology_absent_from_sources_is_not_invented(self):
        sources = [self.source(1, 'ECS disputes the alleged defects. No courier record has been produced.')]
        result = extractive_brief(self.ai, sources, False, self.SYSTEM)
        self.assertEqual(result['coverage']['chronology_units_retained'], 0)
        self.assertNotIn('12 August', result['facts'])
        self.assertNotIn('24 August', result['facts'])
        self.assertEqual(normalised(result['facts']), sources[0]['text'])


if __name__ == '__main__':
    unittest.main()
