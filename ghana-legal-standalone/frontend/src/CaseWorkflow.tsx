import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, FileText, LoaderCircle, Play, RefreshCw, Scale } from 'lucide-react';
import { ApiError, documentUrl, request, type AnalysisJob, type LegalDocument, type LegalReport } from './api';

export default function CaseWorkflow({ matterId, documents, aiConfigured, busy, onBusy, onReport }: {
  matterId: string; documents: LegalDocument[]; aiConfigured: boolean; busy: boolean;
  onBusy: (value: string) => void; onReport: (report: LegalReport | null) => void;
}) {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [now, setNow] = useState(Date.now());
  const callbacks = useRef({ onBusy, onReport });
  callbacks.current = { onBusy, onReport };
  const reported = useRef('');
  const active = job?.status === 'queued' || job?.status === 'running';
  const retrySeconds = job?.retry_at ? Math.max(0, Math.ceil((Date.parse(job.retry_at) - now) / 1000)) : 0;
  useEffect(() => {
    if (!matterId) return;
    let cancelled = false;
    setLoading(true);
    void request<AnalysisJob[]>(`/case-analysis/jobs?matter_id=${encodeURIComponent(matterId)}`).then(items => {
      if (cancelled) return;
      let saved = '';
      try { saved = sessionStorage.getItem(`legal-analysis:${matterId}`) || ''; } catch { /* Storage is optional. */ }
      const current = items.find(item => item.id === saved) || items.find(item => ['queued', 'running', 'paused'].includes(item.status));
      if (current) setJob(current);
    }).catch(e => { if (!cancelled) setError((e as Error).message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [matterId]);
  useEffect(() => {
    if (!job) return;
    try { sessionStorage.setItem(`legal-analysis:${matterId}`, job.id); } catch { /* Storage is optional. */ }
    callbacks.current.onBusy(active ? 'case_workflow' : '');
    if (job.status === 'completed' && job.report && reported.current !== job.report.id) {
      reported.current = job.report.id;
      callbacks.current.onReport(job.report);
    }
    if (!active) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      void request<AnalysisJob>(`/case-analysis/jobs/${job.id}`).then(item => {
        if (!cancelled) { setJob(item); setError(''); }
      }).catch(e => {
        if (!cancelled) { setError((e as Error).message); callbacks.current.onBusy(''); }
      });
    }, 1000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job, active, matterId]);
  useEffect(() => {
    if (!retrySeconds) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [retrySeconds]);
  async function run(resume = false) {
    setError(''); callbacks.current.onBusy('case_workflow');
    if (!resume) { callbacks.current.onReport(null); reported.current = ''; }
    try {
      const result = await request<AnalysisJob>(resume && job ? `/case-analysis/jobs/${job.id}/resume` : '/case-analysis/jobs',
        resume ? {} : { matter_id: matterId });
      setJob(result); setNow(Date.now());
    } catch (e) {
      setError((e as Error).message); callbacks.current.onBusy('');
      if (e instanceof ApiError && e.status === 409 && job) setJob({ ...job, status: 'stale', message: e.message });
    }
  }
  async function refreshStatus() {
    if (!job) return;
    try { setJob(await request<AnalysisJob>(`/case-analysis/jobs/${job.id}`)); setError(''); }
    catch (e) { setError((e as Error).message); }
  }
  return <section className="case-workflow" aria-label="Case analysis workflow">
    <div className="section-heading"><h2>Case documents</h2><span className="tag neutral">Termination and cure</span></div>
    {documents.length ? <ul className="case-document-list">{documents.map(doc => <li key={doc.id}><FileText size={17} /><span>{doc.title}<small>{doc.filename}</small></span><a className="icon-button" href={documentUrl(doc.id)} title={`Download ${doc.title}`} aria-label={`Download ${doc.title}`}><ArrowDownToLine size={17} /></a></li>)}</ul>
      : <p className="muted">{matterId ? 'No case documents uploaded.' : 'No matter selected.'}</p>}
    <div className="form-actions"><button disabled={!matterId || !documents.length || !aiConfigured || busy || active || loading || job?.status === 'paused'} onClick={() => void run()}><Scale size={17} />Analyze Case</button>
      {job?.status === 'paused' && <button className="secondary" disabled={busy || retrySeconds > 0} onClick={() => void run(true)}><Play size={16} />{retrySeconds ? `Resume in ${retrySeconds}s` : 'Resume analysis'}</button>}
    </div>
    {job && <div className="analysis-progress" role="status" aria-live="polite">{active && <LoaderCircle size={17} className="spin" />}<p>{job.message}</p><progress max={100} value={job.progress} aria-label="Case analysis progress" />
      {job.status === 'paused' && <p className="muted">Completed steps are saved. No automatic AI retry will be made.</p>}
    </div>}
    {error && <div className="alert" role="alert">{error}{job && <button className="text-link" onClick={() => void refreshStatus()}><RefreshCw size={15} />Refresh status</button>}</div>}
  </section>;
}
