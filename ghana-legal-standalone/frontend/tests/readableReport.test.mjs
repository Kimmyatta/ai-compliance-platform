import assert from 'node:assert/strict';
import { test } from 'node:test';
import { groupReportClaims, statementAssessment } from '../src/reportPresentation.ts';
import { visibleDraft, visibleObservation } from '../src/caseReportPresentation.ts';

const claim = (changes = {}) => ({ id: 'C1', scope: 'contract_term', text: 'Original wording. Second sentence.', evidence_check: 'matched', check_issues: [], semantic_status: 'not_checked', spans: [], ...changes });

test('grouping retains every claim exactly once and does not write prose or mutate input', () => {
  const claims = ['case_fact', 'contract_term', 'general_principle', 'authority_case_only', 'comparison', 'not_established'].map((scope, i) => claim({ id: `C${i + 1}`, scope }));
  const original = structuredClone(claims);
  const sections = groupReportClaims(claims);
  const rendered = sections.flatMap(section => section.claims);
  assert.deepEqual(rendered, original);
  assert.deepEqual(claims, original);
  assert.ok(rendered.every((item, i) => item === claims[i]));
  assert.equal(sections.find(section => section.title === 'Possible Arguments and Next Steps').claims.length, 0);
  assert.ok(groupReportClaims([]).every(section => section.claims.length === 0 && section.empty));
});

test('supported comparisons, including historical reports, never appear accepted', () => {
  for (const verification of [undefined, { origin: 'policy_gate' }, { origin: 'model' }]) {
    const status = statementAssessment(claim({ scope: 'comparison', semantic_status: 'supported', verification }));
    assert.equal(status.caution, true);
    assert.match(status.label, /Lawyer review required - support not accepted/);
  }
});

test('all evidence and assessment states remain visible and distinguish AI opinion from approval', () => {
  assert.match(statementAssessment(claim()).label, /Not assessed/);
  assert.match(statementAssessment(claim({ semantic_status: 'contradicted' })).label, /AI assessment: contradicted/);
  assert.match(statementAssessment(claim({ semantic_status: 'insufficient_evidence' })).label, /Insufficient evidence/);
  const supported = statementAssessment(claim({ semantic_status: 'supported' }));
  assert.equal(supported.caution, false);
  assert.match(supported.label, /AI assessment: supported - not lawyer-approved/);
  for (const changes of [{ scope: 'not_established' }, { evidence_check: 'no_evidence' }, { verification: { origin: 'evidence_gate' } }]) {
    assert.equal(statementAssessment(claim({ ...changes, semantic_status: 'supported' })).label, 'Insufficient evidence');
  }
  for (const changes of [{ evidence_check: 'flagged' }, { check_issues: ['span_not_found'] }]) {
    assert.match(statementAssessment(claim({ ...changes, semantic_status: 'supported' })).label, /Evidence check failed/);
  }
});

test('case-application gaps appear beside comparisons, once, with their existing warning', () => {
  const claims = [claim({ id: 'C1', scope: 'not_established', application_topic: 'notice_and_cure' }),
    claim({ id: 'C2', scope: 'comparison', application_topic: 'remedial_access' }),
    claim({ id: 'C3', scope: 'not_established' })];
  const sections = groupReportClaims(claims);
  assert.deepEqual(sections.find(s => s.title === 'How They Relate to Your Case').claims.map(c => c.id), ['C1', 'C2']);
  assert.deepEqual(sections.find(s => s.title === 'Uncertainties').claims.map(c => c.id), ['C3']);
  assert.equal(sections.flatMap(s => s.claims).length, claims.length);
  assert.equal(statementAssessment(claims[0]).label, 'Insufficient evidence');
});

test('source alignment is a review question, not automatic legal support', () => {
  const question = claim({ scope: 'not_established', wording_origin: 'review_question', application_alignment: 'aligned_sources', semantic_status: 'supported' });
  assert.equal(statementAssessment(question).label, 'Review question - no legal conclusion');
  assert.equal(statementAssessment({ ...question, application_alignment: 'evidence_gap' }).label, 'Evidence gap - review required');
  assert.match(statementAssessment({ ...question, evidence_check: 'flagged' }).label, /Evidence check failed/);
});

test('support against an entered summary never looks like document or factual verification', () => {
  const oldFact = claim({ scope: 'case_fact', semantic_status: 'supported' });
  assert.equal(statementAssessment(oldFact).caution, true);
  assert.match(statementAssessment(oldFact).label, /entered summary only - not document verification/);
  assert.match(statementAssessment({ ...oldFact, factual_origin: 'case_document' }).label, /document wording - not factual proof/);
});

test('workflow applications need checked source roles and keep positive support unapproved', () => {
  const proposed = claim({ scope: 'comparison', spans: ['facts', 'contract', 'authority'].map((role, i) => ({ role, source_id: i + 1 })),
    verification: { origin: 'policy_gate', model_verdict: 'supported' } });
  assert.equal(visibleDraft(proposed), true);
  for (const changes of [{ verification: { origin: 'model', model_verdict: 'supported' } },
    { verification: { origin: 'policy_gate', model_verdict: 'insufficient_evidence' } },
    { check_issues: ['irrelevant_topic_evidence'] }, { evidence_check: 'flagged' },
    { spans: proposed.spans.slice(1) }, { spans: proposed.spans.map(s => ({ ...s, source_id: null })) }]) {
    assert.equal(visibleDraft({ ...proposed, ...changes }), false);
  }
  assert.equal(visibleObservation(claim({ wording_origin: 'source_text', semantic_status: 'supported' })), true);
  assert.equal(visibleObservation(claim({ wording_origin: 'source_text' })), false);
});
