import { BookOpen, CircleAlert } from 'lucide-react';
import type { EvidenceClaim, EvidenceRole, LegalReport, Source } from './api';

const labels: Record<EvidenceClaim['scope'], string> = {
  contract_term: 'Contract term', case_fact: 'Confirmed factual premise', general_principle: 'Principle in reviewed authority',
  authority_case_only: 'Authority case only', comparison: 'Cross-source comparison', not_established: 'Unresolved point',
};
const roleLabels: Record<EvidenceRole, string> = { contract: 'Contract', authority: 'Authority', facts: 'Confirmed facts' };

function SpanText({ span, text }: { span: EvidenceClaim['spans'][number]; text: string }) {
  if (span.start === null || span.end === null) return <><CircleAlert size={14} />{span.text}<small>Not found in reviewed evidence</small></>;
  // Python indexes Unicode code points; Array.from avoids splitting UTF-16 surrogate pairs.
  const chars = Array.from(text);
  const left = Math.max(0, span.start - 65); const right = Math.min(chars.length, span.end + 65);
  return <>{left > 0 && '...'}{chars.slice(left, span.start).join('')}<mark>{chars.slice(span.start, span.end).join('')}</mark>{chars.slice(span.end, right).join('')}{right < chars.length && '...'}</>;
}

export default function ClaimList({ report, openSource }: { report: LegalReport; openSource: (source: Source) => void }) {
  return <section className="claim-list"><h3>Claims for Review</h3><p className="muted">Text matches and AI assessments are separate checks. Neither is legal validation or lawyer approval.</p>
    {report.payload.claims?.map(claim => <article className="finding atomic-claim" key={claim.id} data-claim-id={claim.id} tabIndex={-1}>
      <span className="finding-number">{claim.id}</span><div>
        <div className="claim-meta"><span className="eyebrow">{claim.factual_origin === 'case_document' ? 'Case-document wording' : labels[claim.scope]}</span><span className={`tag ${claim.evidence_check === 'flagged' ? 'claim-flag' : 'neutral'}`}>{claim.evidence_check === 'matched' ? 'Spans matched / text only' : claim.evidence_check === 'flagged' ? 'Flagged evidence' : 'No establishing evidence'}</span><span className={`tag ${claim.semantic_status === 'contradicted' ? 'claim-flag' : 'neutral'}`} data-assessment={claim.semantic_status}>{claim.verification?.origin === 'policy_gate' || (claim.scope === 'comparison' && claim.semantic_status === 'supported') ? 'Lawyer review required' : claim.verification?.origin === 'evidence_gate' ? 'Evidence gate: unresolved' : claim.scope === 'case_fact' && claim.semantic_status === 'supported' ? 'AI: wording support only' : { not_checked: 'Not assessed', supported: 'AI: supported', contradicted: 'AI: contradicted', insufficient_evidence: 'AI: insufficient evidence' }[claim.semantic_status]}</span></div>
        <p>{claim.text}</p>
        {(claim.verification?.origin === 'policy_gate' || (claim.scope === 'comparison' && claim.semantic_status === 'supported')) && <p className="claim-warning">Cross-source support proposal withheld. Lawyer review required.</p>}
        {claim.check_issues.length > 0 && <p className="claim-warning" role="status">{claim.check_issues.map(issue => ({ missing_required_role: 'Required source role missing', wrong_evidence_role: 'Source role does not match claim scope', span_not_found: 'One or more spans were not found', invalid_evidence_reference: 'Invalid source-text reference', missing_case_fact_reference: 'Case comparison lacks a factual reference', irrelevant_topic_evidence: 'Selected factual excerpt does not match this issue', unresolved_document_reference: 'Factual quotation could not be resolved to one case-document excerpt' }[issue] || issue)).join('. ')}</p>}
        {claim.spans.map((span, index) => {
          const source = report.payload.sources.find(s => s.chunk_id === span.source_id);
          return <div className="claim-span" key={index}><blockquote className="supporting-quote"><span className="eyebrow">{span.role === 'facts' && report.payload.case_evidence ? 'Case-document excerpt, not factual proof' : roleLabels[span.role]}</span><SpanText span={span} text={report.payload.evidence_texts?.[span.role] || ''} /></blockquote>{source && <button className="citation" onClick={() => openSource(source)}><BookOpen size={13} />{source.citation || source.title} / {source.locator}</button>}</div>;
        })}
        {claim.verification && <div className="claim-assessment"><h4>{claim.verification.origin === 'model' ? 'AI Assessment' : 'Assessment Status'}</h4><p>{claim.verification.reason}</p>{claim.scope === 'case_fact' && <p className="claim-warning">This assessment concerns the supplied wording, not whether an allegation is true.</p>}{claim.verification.model_reason && <details><summary>Unaccepted model proposal</summary><p>{claim.verification.model_reason}</p></details>}{claim.verification.evidence.length > 0 && <details><summary>Verifier evidence</summary>{claim.verification.evidence.map((span, index) => <blockquote className="supporting-quote" key={index}><span className="eyebrow">{span.role === 'facts' && report.payload.case_evidence ? 'Case-document excerpt, not factual proof' : roleLabels[span.role]}</span><SpanText span={span} text={report.payload.evidence_texts?.[span.role] || ''} /></blockquote>)}</details>}</div>}
      </div>
    </article>)}
  </section>;
}
