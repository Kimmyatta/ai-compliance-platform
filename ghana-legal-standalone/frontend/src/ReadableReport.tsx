import { BookOpen, CircleAlert } from 'lucide-react';
import type { LegalReport, Source } from './api';
import { applicationLabels, groupReportClaims, statementAssessment } from './reportPresentation';

export default function ReadableReport({ report, openSource, inspectClaim }: {
  report: LegalReport; openSource: (source: Source) => void; inspectClaim: (id: string) => void;
}) {
  return <div className="readable-report">
    <p className="muted report-caution">AI assessments are advisory, not legal validation or lawyer approval. The statements below retain their original wording, including disputed or unsupported conclusions.</p>
    {report.payload.case_evidence && <p className="claim-warning" role="status">{report.payload.case_evidence.warning}{report.payload.case_evidence.coverage.incomplete && ' Only selected excerpts were used; this is not a full-file review.'}</p>}
    {report.payload.verification && ['unavailable', 'partial'].includes(report.payload.verification.state) && <p className="claim-warning" role="status">AI verification incomplete: {report.payload.verification.model_assessed} of {report.payload.verification.eligible_claims} eligible statements assessed. This remains an unverified draft.</p>}
    {groupReportClaims(report.payload.claims || []).map(section => <section className="readable-section" key={section.title} aria-label={section.title}>
      <h3>{section.title}</h3>
      {section.claims.length ? section.claims.map(claim => {
        const assessment = statementAssessment(claim);
        const sourceIds = new Set(claim.spans.map(span => span.source_id));
        const sources = report.payload.sources.filter(source => sourceIds.has(source.chunk_id));
        return <div className={`report-statement${assessment.caution ? ' needs-review' : ''}`} key={claim.id} data-report-claim-id={claim.id}>
          {claim.application_topic && <h4 className="application-topic">{applicationLabels[claim.application_topic]}</h4>}
          {claim.wording_origin === 'source_text' && <span className="eyebrow">{claim.scope === 'case_fact' ? claim.factual_origin === 'case_document' ? 'From the uploaded case document' : 'From the confirmed factual premise' : claim.scope === 'contract_term' ? 'From the reviewed contract' : 'From the reviewed authority'}</span>}
          <p><span className="statement-assessment">{assessment.caution && <CircleAlert size={14} aria-hidden="true" />}{assessment.label}: </span><span className="statement-text">{claim.text}</span></p>
          {claim.wording_origin === 'review_question' && claim.spans.length > 0 && <dl className="application-evidence">{claim.spans.filter(span => !report.payload.case_evidence || span.role !== 'facts').map((span, i) => <div key={i}><dt>{{ contract: 'Contract excerpt', facts: 'Confirmed factual premise', authority: 'Authority excerpt' }[span.role]}</dt><dd>{span.text}</dd></div>)}</dl>}
          {claim.application_topic && report.payload.case_evidence && <div className="topic-case-evidence"><h4>Case-document evidence</h4><p className="muted">Keyword-selected excerpts, not findings or an assessment of legal relevance.</p>{report.payload.case_evidence.units.filter(unit => report.payload.case_evidence!.topics[claim.application_topic!].includes(unit.id)).map(unit => {
            const source = report.payload.sources.find(s => s.chunk_id === unit.source_id);
            return <div key={unit.id}><blockquote className="supporting-quote">{unit.text}</blockquote>{source && <button className="citation" onClick={() => openSource(source)}><BookOpen size={13} />{source.title} / {source.locator}</button>}</div>;
          })}{!report.payload.case_evidence.topics[claim.application_topic].length && <p className="claim-warning">No matching documentary excerpt was selected for this issue. This does not establish that none exists.</p>}</div>}
          <div className="statement-sources">{sources.map(source => <button className="citation" key={source.chunk_id} onClick={() => openSource(source)}><BookOpen size={13} />{source.citation || source.title} / {source.locator}</button>)}
            <button className="icon-button" title="Review evidence for this statement" aria-label="Review evidence for this statement" onClick={() => inspectClaim(claim.id)}><BookOpen size={17} /></button>
          </div>
        </div>;
      }) : <p className="muted section-unavailable">{section.empty}</p>}
    </section>)}
    <section className="readable-section" aria-label="Sources"><h3>Sources</h3>
      <div className="citations">{report.payload.sources.filter(source => report.payload.claims?.some(claim => claim.spans.some(span => span.source_id === source.chunk_id))).map(source => <button className="citation" key={source.chunk_id} onClick={() => openSource(source)}><BookOpen size={13} />{source.citation || source.title} / {source.locator}</button>)}</div>
      {!report.payload.claims?.some(claim => claim.spans.some(span => report.payload.sources.some(source => source.chunk_id === span.source_id))) && <p className="muted section-unavailable">No source passages are linked to the claims in this draft.</p>}
    </section>
  </div>;
}
