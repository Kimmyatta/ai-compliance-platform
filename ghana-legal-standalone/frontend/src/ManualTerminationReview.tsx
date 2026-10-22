import { useEffect, useState, type FormEvent } from 'react';
import { BookOpen, FileSearch, LoaderCircle, Scale } from 'lucide-react';
import { request, type EvidenceRoleReview, type LegalReport, type Source, type TerminationEvidence } from './api';

interface Props {
  matterId: string; facts: string; onFactsChange: (text: string) => void;
  aiConfigured: boolean; busy: boolean; onBusy: (value: string) => void;
  onReport: (report: LegalReport | null) => void; openSource: (source: Source) => void;
  review?: EvidenceRoleReview;
}

export default function ManualTerminationReview({ matterId, facts, onFactsChange, aiConfigured, busy, onBusy, onReport, openSource, review }: Props) {
  const [evidence, setEvidence] = useState<TerminationEvidence | null>(review ? {
    case_passages: [review.contract.source], authority_passages: [review.authority.source], coverage: 'Candidates retained from the blocked automatic selection.',
  } : null);
  const [contractId, setContractId] = useState(review?.contract.source.chunk_id || 0);
  const [authorityId, setAuthorityId] = useState(review?.authority.source.chunk_id || 0);
  const [contractQuote, setContractQuote] = useState(review?.contract.quote || '');
  const [authorityQuote, setAuthorityQuote] = useState(review?.authority.quote || '');
  const [confirmed, setConfirmed] = useState(false);
  const [reasoning, setReasoning] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setConfirmed(false); setReasoning(false); }, [facts]);

  function invalidate() { setConfirmed(false); setReasoning(false); onReport(null); }
  async function loadEvidence() {
    onBusy('evidence'); setError(''); invalidate();
    setEvidence(null); setContractId(0); setAuthorityId(0); setContractQuote(''); setAuthorityQuote('');
    try { setEvidence(await request<TerminationEvidence>('/case-analysis/termination/evidence', { matter_id: matterId })); }
    catch (e) { setError((e as Error).message); }
    finally { onBusy(''); }
  }
  async function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); onBusy('termination'); setError(''); onReport(null);
    try {
      onReport(await request<LegalReport>('/case-analysis/termination', {
        matter_id: matterId, facts, contract: { source_id: contractId, quote: contractQuote },
        authority: { source_id: authorityId, quote: authorityQuote }, confirmed, reasoning_confirmed: reasoning,
        ...(review ? { role_review_id: review.review_id } : {}),
      }));
    } catch (e) { setError((e as Error).message); }
    finally { onBusy(''); }
  }

  function selection(role: 'contract' | 'authority') {
    const sources = (role === 'contract' ? evidence?.case_passages : evidence?.authority_passages) || [];
    const id = role === 'contract' ? contractId : authorityId;
    const quote = role === 'contract' ? contractQuote : authorityQuote;
    const source = sources.find(s => s.chunk_id === id);
    const name = role === 'contract' ? 'Contract clause' : 'Authority reasoning';
    return <section className="evidence-review">
      <h3>{name}</h3>
      <label>{name} passage<select disabled={busy} required value={id || ''} onChange={e => {
        const next = Number(e.target.value); const text = sources.find(s => s.chunk_id === next)?.text || '';
        if (role === 'contract') { setContractId(next); setContractQuote(text); }
        else { setAuthorityId(next); setAuthorityQuote(text); }
        invalidate();
      }}><option value="">Select a passage</option>{sources.map(s => <option key={s.chunk_id} value={s.chunk_id}>{s.citation || s.title} / {s.locator} / #{s.chunk_id}</option>)}</select></label>
      {source && <>
        <label>Reviewed {role === 'contract' ? 'contract' : 'authority'} quotation<textarea disabled={busy} required minLength={20} maxLength={3000} value={quote} onChange={e => {
          if (role === 'contract') setContractQuote(e.target.value); else setAuthorityQuote(e.target.value);
          invalidate();
        }} /></label>
        <button type="button" className="text-link" onClick={() => openSource(source)}><BookOpen size={15} />View original passage</button>
        <details><summary>Available surrounding passages</summary><div className="citations">{sources.filter(s => s.document_id === source.document_id).sort((a, b) => a.chunk_id - b.chunk_id).map(s => <button className="citation" type="button" key={s.chunk_id} onClick={() => openSource(s)}>{s.locator} / #{s.chunk_id}</button>)}</div></details>
      </>}
      {!sources.length && evidence && <p className="muted">{role === 'contract' ? 'No matching case-file passages. Upload the agreement to this matter.' : 'No matching authorities. Add relevant judgments or statutes to the legal library.'}</p>}
    </section>;
  }

  return <div className="termination-review">
    <div className="section-heading"><h2>Manual evidence review</h2><button className="secondary" type="button" disabled={!matterId || busy} onClick={() => void loadEvidence()}><FileSearch size={16} />Find review passages</button></div>
    {review && <div className="brief-notes"><h3>Earlier automatic selection was flagged</h3><ul>{review.issues.map((issue, i) => <li key={i}>{issue.message}</li>)}</ul></div>}
    <form className="case-form" onSubmit={compare}>
      <label>Focused case facts<textarea required minLength={10} maxLength={4000} disabled={busy} value={facts} onChange={e => { onFactsChange(e.target.value); invalidate(); }} /></label>
      {evidence && <><p className="muted">{evidence.coverage}</p><div className="review-grid">{selection('contract')}{selection('authority')}</div></>}
      <label className="checkbox"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} />I have reviewed the facts and the exact contract clause, including its notice and cure wording.</label>
      <label className="checkbox"><input type="checkbox" checked={reasoning} disabled={busy} onChange={e => setReasoning(e.target.checked)} />The selected authority quotation contains relevant court reasoning or statutory text, not merely a party's allegations.</label>
      <div className="form-actions"><button type="submit" disabled={busy || !aiConfigured || !contractId || !authorityId || !confirmed || !reasoning || facts.trim().length < 10}><Scale size={16} />Compare termination issue</button>{busy && <LoaderCircle size={18} className="spin" />}</div>
      {error && <div className="alert" role="alert">{error}</div>}
    </form>
  </div>;
}
