import { BookOpen, CircleAlert } from 'lucide-react';
import type { EvidenceClaim, LegalReport, Source, WorkflowIssue } from './api';
import { visibleDraft, visibleObservation } from './caseReportPresentation';

const kindLabels: Record<string, string> = { reasoning: 'Court reasoning', decision: 'Decision in the cited case', principle: 'Principle stated in the excerpt',
  similarity: 'Similarity', difference: 'Important difference', argument_for_termination: 'For the party seeking termination',
  argument_against_termination: 'For the party resisting termination', weakness: 'Weakness or limitation' };

export default function CaseWorkflowReport({ report, openSource }: { report: LegalReport; openSource: (source: Source) => void }) {
  const { payload } = report;
  const issues = payload.issue_reports || [];
  function citations(ids: (number | null)[]) {
    const unique = new Set(ids);
    return <div className="statement-sources">{payload.sources.filter(source => unique.has(source.chunk_id)).map(source => <button className="citation" key={source.chunk_id} onClick={() => openSource(source)}><BookOpen size={13} />{source.citation || source.title} / {source.locator}</button>)}</div>;
  }
  function statement(claim: EvidenceClaim) {
    const visible = visibleDraft(claim) || visibleObservation(claim);
    return <div className={`report-statement${claim.scope === 'comparison' || !visible ? ' needs-review' : ''}`} key={claim.id}>
      <span className="eyebrow">{kindLabels[claim.report_kind || ''] || 'Evidence gap'}</span>
      <p>{visible ? claim.text : claim.scope === 'not_established' && claim.evidence_check !== 'flagged'
        ? claim.text : 'A draft statement was withheld because its evidence or AI assessment did not establish support.'}</p>
      <p className="claim-warning"><CircleAlert size={13} /> {visibleDraft(claim) ? 'Draft for lawyer review, not an accepted legal conclusion.'
        : visibleObservation(claim) ? 'Quoted source; applicability and current status unconfirmed.' : 'Unresolved within the reviewed excerpts.'}</p>
      {citations(claim.spans.map(span => span.source_id))}
    </div>;
  }
  function applicationSection(issue: WorkflowIssue, kinds: string[]) {
    const claims = issue.claims.filter(c => kinds.includes(c.report_kind || ''));
    return <div className="workflow-issue" key={issue.key}><h4>{issue.title}</h4>{claims.length ? claims.map(statement)
      : <p className="claim-warning">No application passed this issue's evidence checks. Review the gaps below.</p>}</div>;
  }
  return <div className="readable-report workflow-report">
    <p className="claim-warning">{payload.warning}</p><p className="muted">{payload.scope}</p>
    <section className="readable-section" aria-label="Case Summary"><h3>Case Summary</h3><p className="muted">Excerpts from the uploaded case documents, not independently proven facts.</p>
      {payload.brief?.fact_excerpts?.map(unit => <div className="report-statement" key={unit.id}><p>{unit.text}</p>{citations([unit.source_id])}</div>)}
      {payload.brief?.truncated && <p className="claim-warning">The factual brief uses selected excerpts, not the complete case file.</p>}
    </section>
    <section className="readable-section" aria-label="Legal Issues"><h3>Legal Issues</h3><ul>{issues.map(issue => <li key={issue.key}>{issue.title}</li>)}</ul></section>
    <section className="readable-section" aria-label="Relevant Judgments"><h3>Relevant Judgments</h3>{issues.map(issue => <div className="workflow-issue" key={issue.key}><h4>{issue.title}</h4>
      {issue.claims.filter(c => ['reasoning', 'decision', 'principle'].includes(c.report_kind || '')).map(statement)}
      {!issue.claims.some(c => c.report_kind === 'decision' && visibleObservation(c)) && <p className="claim-warning">No court-decision excerpt passed the checks for this issue. This does not establish that the original judgment lacks a decision.</p>}
      {citations(issue.sources.filter(s => s.kind !== 'matter').map(s => s.chunk_id))}
    </div>)}</section>
    <section className="readable-section" aria-label="How They Apply"><h3>How They Apply</h3>{issues.map(issue => applicationSection(issue, ['similarity', 'difference']))}</section>
    <section className="readable-section" aria-label="Arguments and Weaknesses"><h3>Arguments and Weaknesses</h3>{issues.map(issue => applicationSection(issue, ['argument_for_termination', 'argument_against_termination', 'weakness']))}</section>
    <section className="readable-section" aria-label="Missing Evidence"><h3>Missing Evidence</h3>{issues.map(issue => <div className="workflow-issue" key={issue.key}><h4>{issue.title}</h4>
      {issue.notes.map((note, i) => <p className="claim-warning" key={i}>{note}</p>)}
      {issue.claims.filter(c => !visibleDraft(c) && !visibleObservation(c)).map(c => <p className="muted" key={c.id}>{kindLabels[c.report_kind || '']}: {c.scope === 'not_established' && c.evidence_check !== 'flagged' ? c.text : 'The draft evidence or assessment did not establish this statement.'}</p>)}
      {!issue.notes.length && issue.claims.every(c => visibleDraft(c) || visibleObservation(c)) && <p className="muted">No additional gap was recorded in these excerpts. This is not a complete-evidence finding.</p>}
    </div>)}</section>
    <details className="supporting-evidence"><summary>Review supporting evidence</summary>{issues.map(issue => <section className="readable-section" key={issue.key}><h3>{issue.title}</h3>
      {issue.coverage && <p className="muted">Authority candidates assessed: {issue.coverage.assessed ?? 0} of {issue.coverage.candidates ?? 0}. Case excerpts supplied: {issue.coverage.issue_units_selected ?? 0} of {issue.coverage.issue_units_available ?? 0} selected candidates.</p>}
      {issue.selected_evidence && (['contract', 'authority'] as const).map(role => <div key={role}><blockquote className="supporting-quote"><span className="eyebrow">Selected {role} quotation / role assessment is fallible</span>{issue.selected_evidence![role].quote}</blockquote>{citations([issue.selected_evidence![role].source_id])}</div>)}
      {issue.claims.map(claim => <div className="report-statement" key={claim.id}><span className="eyebrow">{kindLabels[claim.report_kind || '']} / {claim.evidence_check} / {claim.semantic_status}</span><p className="claim-warning">Original draft for inspection, not an accepted conclusion.</p><p>{claim.text}</p>
        {claim.verification && <p className="muted">{claim.verification.reason}</p>}
        {claim.spans.map((span, i) => <div key={i}><blockquote className="supporting-quote"><span className="eyebrow">{span.role === 'facts' ? 'Case-document excerpt' : span.role}</span>{span.text}</blockquote>{citations([span.source_id])}</div>)}
      </div>)}
    </section>)}</details>
  </div>;
}
