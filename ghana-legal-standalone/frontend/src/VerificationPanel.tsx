import { useEffect, useState } from 'react';
import { LoaderCircle, RefreshCw } from 'lucide-react';
import type { LegalReport } from './api';

export default function VerificationPanel({ report, busy, run }: { report: LegalReport; busy: boolean; run: () => void }) {
  const [now, setNow] = useState(Date.now());
  const info = report.payload.verification;
  const retryAt = info?.retry_after ? Date.parse(info.created_at) + info.retry_after * 1000 : 0;
  const seconds = Math.max(0, Math.ceil((retryAt - now) / 1000));
  useEffect(() => {
    setNow(Date.now());
    if (!retryAt || retryAt <= Date.now()) return;
    const timer = setInterval(() => {
      const current = Date.now(); setNow(current);
      if (current >= retryAt) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [retryAt]);
  const eligible = report.payload.claims?.some(c => c.evidence_check === 'matched' && c.scope !== 'not_established');
  const withheld = info?.withheld_model_support ?? report.payload.claims?.filter(c => c.scope === 'comparison' && c.semantic_status === 'supported').length ?? 0;
  return <section className="verification-panel" aria-label="AI claim verification">
    <div className="section-heading"><h3>AI Claim Check</h3><button className="secondary verify-command" disabled={busy || seconds > 0 || !eligible} onClick={run}>{busy ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}Verify claims</button></div>
    {info ? <><p className="muted">{info.model_assessed} of {info.eligible_claims} eligible claims assessed by {info.model}. {info.blocked_claims} blocked; {info.gate_assessed} unresolved.</p><span className="tag neutral">{{ complete: 'Assessment pass completed', partial: 'Partial assessment', unavailable: 'Verifier unavailable', skipped: 'No eligible claims' }[info.state]}</span><p className="muted">{info.warning}</p>{info.notes.map((note, i) => <p className="claim-warning" key={i}>{note}</p>)}</> : <p className="muted">No verifier pass is recorded for this draft. Claims remain unassessed.</p>}
    {seconds > 0 && <p className="muted" role="status">Retry verification in {seconds}s.</p>}
    {withheld > 0 && <p className="claim-warning">{withheld} cross-source support proposal(s) withheld for lawyer review.</p>}
  </section>;
}
