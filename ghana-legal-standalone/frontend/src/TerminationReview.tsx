import { useEffect, useRef, useState, type FormEvent } from 'react';
import { BookOpen, FileSearch, LoaderCircle, Scale } from 'lucide-react';
import { aiRetryUntil, ApiError, blockedEvidenceReview, request, type AutomaticEvidence, type EvidenceRoleReview, type LegalReport, type Source } from './api';
import ManualTerminationReview from './ManualTerminationReview';

interface Props {
  matterId: string; facts: string; onFactsChange: (text: string) => void;
  aiConfigured: boolean; busy: boolean; onBusy: (value: string) => void;
  onReport: (report: LegalReport | null) => void; openSource: (source: Source) => void;
}

export default function TerminationReview(props: Props) {
  const { matterId, facts, onFactsChange, aiConfigured, busy, onBusy, onReport, openSource } = props;
  const [evidence, setEvidence] = useState<AutomaticEvidence | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [manual, setManual] = useState(false);
  const [blockedReview, setBlockedReview] = useState<EvidenceRoleReview | null>(null);
  const manualDetails = useRef<HTMLDetailsElement>(null);
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());
  const [retryAt, setRetryAt] = useState(aiRetryUntil);
  useEffect(() => { setRetryAt(aiRetryUntil()); }, [busy]);
  useEffect(() => {
    setNow(Date.now());
    if (retryAt <= Date.now()) return;
    const timer = setInterval(() => {
      const current = Date.now(); setNow(current);
      if (current >= retryAt) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [retryAt]);
  const retrySeconds = Math.max(0, Math.ceil((retryAt - now) / 1000));
  function showError(e: unknown) {
    setBlockedReview(blockedEvidenceReview(e));
    setRetryAt(aiRetryUntil());
    setError(e instanceof ApiError && e.status === 429
      ? 'Groq is temporarily rate-limited. Retry when the countdown finishes; completed evidence-selection stages are kept.'
      : (e as Error).message);
  }
  useEffect(() => { setEvidence(null); setConfirmed(false); setError(''); }, [facts]);
  useEffect(() => {
    if (!evidence) return;
    setNow(Date.now());
    if (Date.parse(evidence.expires_at) <= Date.now()) return;
    const timer = setInterval(() => {
      const current = Date.now(); setNow(current);
      if (Date.parse(evidence.expires_at) <= current) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [evidence]);
  const expired = evidence ? Date.parse(evidence.expires_at) <= now : false;

  async function prepare() {
    if (retrySeconds > 0) return;
    onBusy('evidence'); setError(''); setBlockedReview(null); setEvidence(null); setConfirmed(false); onReport(null);
    try { setEvidence(await request<AutomaticEvidence>('/case-analysis/termination/prepare', { matter_id: matterId, facts })); }
    catch (e) { showError(e); }
    finally { onBusy(''); }
  }
  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!evidence || expired || !confirmed || retrySeconds > 0) return;
    onBusy('termination'); setError(''); onReport(null);
    try {
      onReport(await request<LegalReport>('/case-analysis/termination/automatic', {
        matter_id: matterId, facts, selection_id: evidence.selection_id, confirmed,
      }));
    } catch (e) { showError(e); }
    finally { onBusy(''); }
  }

  return <div className="termination-review">
    {!manual && <>
      <h2>Termination, Notice and Cure</h2>
      <form className="case-form automatic-review" onSubmit={generate}>
        <label>Case facts<textarea required minLength={10} maxLength={4000} disabled={busy} value={facts} onChange={e => { onFactsChange(e.target.value); setEvidence(null); setConfirmed(false); onReport(null); }} /></label>
        <div className="form-actions"><button className="secondary" type="button" disabled={!matterId || busy || !aiConfigured || retrySeconds > 0 || facts.trim().length < 10} onClick={() => void prepare()}><FileSearch size={16} />Find relevant evidence</button>{busy && <LoaderCircle size={18} className="spin" />}</div>
        {evidence && <section className="automatic-evidence" aria-label="Selected evidence">
          <h3>Selected evidence</h3><p className="claim-warning">{evidence.warning}</p>
          <p className="muted">{evidence.coverage.note} AI assessed {evidence.coverage.contract.assessed} of {evidence.coverage.contract.candidates} contract candidates and {evidence.coverage.authority.assessed} of {evidence.coverage.authority.candidates} authority candidates.</p>
          <div className="review-grid">{(['contract', 'authority'] as const).map(role => {
            const item = evidence[role];
            return <div key={role}><blockquote className="supporting-quote"><span className="eyebrow">{role === 'contract' ? 'AI-selected contract clause' : item.role === 'statutory_text' ? 'Statutory text / AI role assessment' : 'Court reasoning / AI role assessment'}</span>{item.quote}</blockquote>
              <button type="button" className="citation" onClick={() => openSource(item.source)}><BookOpen size={13} />{item.source.citation || item.source.title} / {item.source.locator}</button></div>;
          })}</div>
        </section>}
        {evidence && <label className="checkbox"><input type="checkbox" checked={confirmed} disabled={busy || expired} onChange={e => setConfirmed(e.target.checked)} />I have reviewed and confirmed these case facts, including any disputed allegations.</label>}
        {expired && <p className="claim-warning" role="status">This evidence preview has expired. Find relevant evidence again.</p>}
        <div className="form-actions"><button type="submit" disabled={busy || !aiConfigured || !evidence || !confirmed || expired || retrySeconds > 0}><Scale size={16} />Generate case report</button></div>
        {retrySeconds > 0 && <p className="muted" role="status">Retry AI requests in {retrySeconds}s. No automatic retry will be made.</p>}
        {error && <div className="alert" role="alert">{error}</div>}
        {blockedReview && <section className="automatic-evidence blocked-evidence" aria-label="Evidence requiring review">
          <h3>Evidence requiring review</h3><ul>{blockedReview.issues.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul>
          <p className="muted">This is an AI selection or attribution failure, not a finding that no relevant law exists.</p>
          <div className="review-grid">{(['contract', 'authority'] as const).map(role => {
            const item = blockedReview[role];
            return <div key={role}><blockquote className="supporting-quote"><span className="eyebrow">{role === 'contract' ? 'Contract candidate / not approved' : 'Authority candidate / not approved'}</span>{item.quote}</blockquote>
              <button type="button" className="citation" onClick={() => openSource(item.source)}><BookOpen size={13} />{item.source.citation || item.source.title} / {item.source.locator}</button></div>;
          })}</div>
          <button type="button" className="secondary" disabled={busy} onClick={() => { if (manualDetails.current) manualDetails.current.open = true; }}><BookOpen size={16} />Review selected passages</button>
        </section>}
      </form>
    </>}
    <details ref={manualDetails} className="manual-evidence" onToggle={e => {
      const open = e.currentTarget.open; setManual(open); setEvidence(null); setConfirmed(false); setError(''); onReport(null);
    }}><summary onClick={e => { if (busy) e.preventDefault(); }} aria-disabled={busy}>Manual evidence review</summary>{manual && <ManualTerminationReview {...props} review={blockedReview || undefined} />}</details>
  </div>;
}
