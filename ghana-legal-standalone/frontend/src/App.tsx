import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import {
  ArrowDownToLine, ArrowRight, BookOpen, Check, ChevronRight, CircleAlert,
  FileSearch, FileText, FolderOpen, Gavel, LayoutDashboard, LoaderCircle,
  Menu, Plus, RefreshCw, Scale, Search, Upload, X,
} from 'lucide-react';
import { documentUrl, downloadReport, request, type Brief, type Dashboard, type Health,
  type LegalDocument, type LegalReport, type Matter, type Source } from './api';
import TerminationReview from './TerminationReview';
import ClaimList from './ClaimList';
import VerificationPanel from './VerificationPanel';
import ReadableReport from './ReadableReport';
import CaseWorkflow from './CaseWorkflow';
import CaseWorkflowReport from './CaseWorkflowReport';

const navigation = [
  { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
  { id: 'research', label: 'Legal Research', icon: Search },
  { id: 'analysis', label: 'Case Analysis', icon: FileSearch },
  { id: 'documents', label: 'Documents', icon: BookOpen },
  { id: 'matters', label: 'Matters', icon: FolderOpen },
  { id: 'reports', label: 'Reports', icon: FileText },
] as const;
type Page = typeof navigation[number]['id'];
const date = (value: string) => new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const kindLabel = (kind: string) => ({ judgment: 'Judgment', statute: 'Statute', matter: 'Matter file' }[kind] || kind);

function Empty({ icon, title, action }: { icon: ReactNode; title: string; action?: ReactNode }) {
  return <div className="empty">{icon}<p>{title}</p>{action}</div>;
}

function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className="modal" onCancel={close} onClick={e => { if (e.target === ref.current) close(); }}>
    <div className="modal-header"><h2>{title}</h2><button type="button" className="icon-button" title="Close" aria-label="Close" onClick={close}><X size={20} /></button></div>
    {children}
  </dialog>;
}

function SourceView({ source, close }: { source: Source; close: () => void }) {
  return <Modal title="Source passage" close={close}>
    <div className="source-heading"><span className="eyebrow">{kindLabel(source.kind)} / {source.locator}</span>
      <h3>{source.title}</h3><p>{[source.citation, source.court, source.decision_date].filter(Boolean).join(' / ')}</p></div>
    <blockquote className="source-text">{source.text}</blockquote>
    <div className="modal-footer"><a className="button secondary" href={documentUrl(source.document_id)}><ArrowDownToLine size={16} />Original document</a>
      {source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer" className="text-link">Publisher source <ArrowRight size={15} /></a>}</div>
  </Modal>;
}

function Report({ report, openSource, onVerified, onVerifyBusy }: { report: LegalReport; openSource: (source: Source) => void; onVerified: (report: LegalReport) => void; onVerifyBusy: (value: string) => void }) {
  const [verifying, setVerifying] = useState(false);
  const [verificationError, setVerificationError] = useState('');
  const evidenceDetails = useRef<HTMLDetailsElement>(null);
  const atomic = report.payload.workflow === 'termination_atomic_v2' && Array.isArray(report.payload.claims);
  function inspectClaim(id: string) {
    if (!evidenceDetails.current) return;
    evidenceDetails.current.open = true;
    const target = Array.from(evidenceDetails.current.querySelectorAll<HTMLElement>('[data-claim-id]')).find(element => element.dataset.claimId === id);
    target?.focus({ preventScroll: true });
    target?.scrollIntoView({ block: 'center' });
  }
  async function verify() {
    setVerifying(true); onVerifyBusy('verification'); setVerificationError('');
    try { onVerified(await request<LegalReport>(`/reports/${report.id}/verify`, {})); }
    catch (e) { setVerificationError((e as Error).message); }
    finally { setVerifying(false); onVerifyBusy(''); }
  }
  if (report.payload.workflow === 'case_workflow_v1') return <article className="report">
    <div className="alert" role="alert">AI-generated draft. Lawyer review required before relying on any argument or conclusion.</div>
    <div className="section-heading"><div><span className="eyebrow">Case analysis / {date(report.created_at)}</span><h2>{report.payload.title}</h2></div><button className="icon-button" title="Download report JSON" aria-label="Download report JSON" onClick={() => downloadReport(report)}><ArrowDownToLine size={19} /></button></div>
    <CaseWorkflowReport report={report} openSource={openSource} />
    <div className="limitations"><h3>Review notes</h3><ul>{report.payload.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul></div>
  </article>;
  return <article className="report">
    {report.kind === 'case_analysis' && <div className="alert" role="alert">AI-generated draft. Quotations do not verify legal conclusions or contract interpretation. Lawyer review required.</div>}
    {report.payload.evidence_selection && <div className="alert" role="alert">{report.payload.evidence_selection.warning}</div>}
    {report.payload.evidence_selection?.original_issues && <div className="brief-notes"><h3>Earlier automatic selection flags</h3><ul>{report.payload.evidence_selection.original_issues.map((issue, i) => <li key={i}>{issue.message}</li>)}</ul></div>}
    {report.kind === 'case_analysis' && report.payload.workflow !== 'termination_atomic_v2' && <div className="alert" role="alert">Legacy paragraph-format report. It has not passed claim-level evidence checks. Do not rely on it; regenerate through the reviewed-evidence workflow.</div>}
    <div className="section-heading"><div><span className="eyebrow">{report.kind === 'research' ? 'Research report' : 'Case analysis'} / {date(report.created_at)}</span><h2>{atomic ? 'Termination and cure' : report.payload.title}</h2></div>
      <button className="icon-button" title="Download report JSON" aria-label="Download report JSON" onClick={() => downloadReport(report)}><ArrowDownToLine size={19} /></button></div>
    {atomic && <ReadableReport report={report} openSource={openSource} inspectClaim={inspectClaim} />}
    <details key={report.id} ref={evidenceDetails} className="supporting-evidence" open={atomic ? undefined : true}>
    <summary>{atomic ? 'Review supporting evidence' : 'Report evidence and findings'}</summary>
    {report.payload.confirmed_facts && <details><summary>{report.payload.case_evidence ? 'Entered summary and issues (not documentary proof)' : 'Confirmed case facts and issues'}</summary><p>{report.payload.confirmed_facts}</p><ul>{report.payload.confirmed_issues?.map((issue, i) => <li key={i}>{issue}</li>)}</ul></details>}
    {report.payload.reviewed_evidence && <section className="reviewed-evidence"><h3>Reviewed Evidence</h3><span className="tag neutral">{report.payload.claims ? 'Claim set / lawyer review required' : report.payload.comparison?.status === 'insufficient_authority' ? 'Insufficient authority' : 'Limited comparison / unverified draft'}</span><div className="review-grid">{(['contract', 'authority'] as const).map(role => {
      const quote = report.payload.reviewed_evidence![role];
      const source = report.payload.sources.find(s => s.chunk_id === quote.source_id);
      return <div key={role}><blockquote className="supporting-quote"><span className="eyebrow">{role === 'contract' ? 'Reviewed contract clause' : 'Reviewed authority reasoning'}</span>{quote.quote}</blockquote>{source && <button className="citation" onClick={() => openSource(source)}><BookOpen size={13} />{source.citation || source.title} / {source.locator}</button>}</div>;
    })}</div></section>}
    {report.payload.claims && <><VerificationPanel report={report} busy={verifying} run={() => void verify()} />{verificationError && <div className="alert" role="alert">{verificationError}</div>}<ClaimList report={report} openSource={openSource} /></>}
    {!atomic && report.payload.findings.map((finding, i) => <section className="finding" key={i}>
      <span className="finding-number">{String(i + 1).padStart(2, '0')}</span>
      <div>{finding.category && <span className="eyebrow">{{ comparison: 'Authority comparison', possible_approach: 'Possible legal approach', evidence_gap: 'Evidence gap' }[finding.category]}</span>}<p>{finding.text}</p>{finding.supporting_quotes?.map((quote, q) => <blockquote key={q} className="supporting-quote"><span className="eyebrow">Quoted authority</span>{quote.quote}</blockquote>)}<div className="citations">{finding.source_ids.map((id, j) => {
        const source = report.payload.sources.find(s => s.chunk_id === id);
        return source && <button className="citation" key={`${id}-${j}`} onClick={() => openSource(source)} title={`${source.title}, ${source.locator}`}><BookOpen size={13} />{source.kind === 'matter' ? 'Case file: ' : ''}{source.citation || source.title} / {source.locator}</button>;
      })}</div></div>
    </section>)}
    </details>
    <div className="limitations"><h3>Review notes</h3><ul>{report.payload.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul></div>
  </article>;
}

function DocumentTable({ documents, matters }: { documents: LegalDocument[]; matters: Matter[] }) {
  return <div className="table-wrap"><table><thead><tr><th>Document</th><th>Collection</th><th>Location / authority</th><th>Added</th><th><span className="sr-only">Download</span></th></tr></thead>
    <tbody>{documents.map(document => <tr key={document.id}>
      <td><div className="document-title"><FileText size={18} /><div><strong>{document.title}</strong><small>{document.citation || document.filename}</small></div></div></td>
      <td><span className={`tag ${document.kind === 'matter' ? 'neutral' : ''}`}>{kindLabel(document.kind)}</span></td>
      <td>{document.kind === 'matter' ? matters.find(m => m.id === document.matter_id)?.name : document.court || 'Ghana'}</td>
      <td className="nowrap">{date(document.created_at)}</td>
      <td><a className="icon-button" title={`Download ${document.title}`} aria-label={`Download ${document.title}`} href={documentUrl(document.id)}><ArrowDownToLine size={17} /></a></td>
    </tr>)}</tbody></table></div>;
}

function UploadForm({ matters, onDone, initialMatter, initialKind = 'judgment' }: { matters: Matter[]; onDone: () => void; initialMatter: string; initialKind?: string }) {
  const [kind, setKind] = useState(initialKind);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError('Choose a document.'); return; }
    if (file.size > 20 * 1024 * 1024) { setError('Upload a document smaller than 20 MB.'); return; }
    setBusy(true); setError('');
    const body = new FormData(event.currentTarget);
    body.set('file', file);
    body.set('permission_confirmed', 'true');
    try { await request('/documents', body); onDone(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <form className="form-stack" onSubmit={submit}>
    <label className="file-picker"><Upload size={27} /><strong>{file?.name || 'Choose a document'}</strong><span>PDF, DOCX or TXT / up to 20 MB</span>
      <input type="file" name="file" accept=".pdf,.docx,.txt" required onChange={e => setFile(e.target.files?.[0] || null)} /></label>
    <label>Document title<input name="title" maxLength={240} placeholder="Optional" /></label>
    <label>Collection<select name="kind" value={kind} onChange={e => setKind(e.target.value)}><option value="judgment">Legal library / Judgment</option><option value="statute">Legal library / Statute</option><option value="matter">Private matter file</option></select></label>
    {kind === 'matter' ? <label>Matter<select name="matter_id" defaultValue={initialMatter} required><option value="">Select a matter</option>{matters.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label> : <>
      <div className="form-grid"><label>Court / issuing body<input name="court" maxLength={160} /></label><label>Decision / enactment date<input name="decision_date" type="date" /></label></div>
      <label>Official citation<input name="citation" maxLength={240} /></label>
      <label>Source URL<input name="source_url" type="url" placeholder="https://" maxLength={2000} /></label>
    </>}
    <label>Permission / provenance note<input name="permission_note" maxLength={1000} placeholder="Source or basis for permitted use" /></label>
    <label className="checkbox"><input type="checkbox" required />I am authorised to store and process this document.{kind !== 'matter' && ' It may be searched across matters in this workspace.'}</label>
    {error && <div className="alert" role="alert">{error}</div>}
    <div className="modal-footer"><button disabled={busy} type="submit">{busy ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}{busy ? 'Processing document...' : 'Upload document'}</button></div>
  </form>;
}

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [mobileNav, setMobileNav] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [matters, setMatters] = useState<Matter[]>([]);
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [reports, setReports] = useState<LegalReport[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState<'upload' | 'matter' | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [matterId, setMatterId] = useState('');
  const [filter, setFilter] = useState('library');
  const [documentQuery, setDocumentQuery] = useState('');
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState('library');
  const [results, setResults] = useState<Source[] | null>(null);
  const [report, setReport] = useState<LegalReport | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [facts, setFacts] = useState('');
  const [issues, setIssues] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<'termination' | 'general'>('termination');
  const [advancedAnalysis, setAdvancedAnalysis] = useState(false);
  const [busy, setBusy] = useState('');
  const [actionError, setActionError] = useState('');
  const [matterError, setMatterError] = useState('');

  async function reload() {
    setLoading(true);
    try {
      const [h, d, m, docs, saved] = await Promise.all([
        request<Health>('/health'), request<Dashboard>('/dashboard'), request<Matter[]>('/matters'),
        request<LegalDocument[]>('/documents'), request<LegalReport[]>('/reports'),
      ]);
      setHealth(h); setDashboard(d); setMatters(m); setDocuments(docs); setReports(saved); setError('');
    } catch { setHealth(null); setError('Workspace unavailable. Check that the legal API is running.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void reload(); }, []);
  function navigate(next: Page) { if (busy) return; setPage(next); setMobileNav(false); setActionError(''); setReport(null); }
  function changeMatter(id: string) { setMatterId(id); setBrief(null); setFacts(''); setIssues(''); setConfirmed(false); setReport(null); setResults(null); }
  function openReport(item: LegalReport) { setPage('reports'); setReport(item); }
  function verifiedReport(item: LegalReport) { setReport(item); void reload(); }

  async function research(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setActionError(''); setBusy('search'); setReport(null); setResults(null);
    const mode = (event.nativeEvent as SubmitEvent).submitter?.getAttribute('value') || 'search';
    try {
      const body = { query: query.trim(), scope, matter_id: matterId || null };
      if (mode === 'answer') {
        setReport(await request<LegalReport>('/research', body));
        await reload();
      } else setResults(await request<Source[]>('/search', body));
    } catch (e) { setActionError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function prepareBrief() {
    setActionError(''); setBusy('brief'); setReport(null); setBrief(null); setConfirmed(false);
    try {
      const item = await request<Brief>('/case-analysis/brief', { matter_id: matterId });
      setBrief(item); setFacts(item.facts); setIssues(item.issues.join('\n'));
    } catch (e) { setActionError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setActionError(''); setBusy('analysis'); setReport(null);
    try {
      setReport(await request<LegalReport>('/case-analysis', { matter_id: matterId, facts,
        issues: issues.split('\n').map(i => i.trim()).filter(Boolean), confirmed }));
      await reload();
    } catch (e) { setActionError((e as Error).message); }
    finally { setBusy(''); }
  }
  async function createMatter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy('matter'); setMatterError('');
    const data = new FormData(event.currentTarget);
    try {
      const matter = await request<Matter>('/matters', Object.fromEntries(data));
      changeMatter(matter.id); setModal(null); setNotice('Matter created.'); await reload();
    } catch (e) { setMatterError((e as Error).message); }
    finally { setBusy(''); }
  }

  const selectedMatter = matters.find(m => m.id === matterId);
  const filteredDocs = documents.filter(d => (filter === 'library' ? d.kind !== 'matter' : d.kind === 'matter')
    && (filter === 'library' || !matterId || d.matter_id === matterId)
    && `${d.title} ${d.filename} ${d.citation}`.toLowerCase().includes(documentQuery.toLowerCase()));
  const pageTitle = navigation.find(n => n.id === page)!.label;
  const matterSelect = (required = false) => <select aria-label="Matter" value={matterId} required={required} disabled={!!busy} onChange={e => changeMatter(e.target.value)}><option value="">{required ? 'Select a matter' : 'All matters'}</option>{matters.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select>;
  const uploadButton = <button onClick={() => setModal('upload')} disabled={!health || !!busy}><Upload size={16} />Upload document</button>;

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
      <a href="#overview" className="brand" onClick={e => { e.preventDefault(); navigate('dashboard'); }}><span className="brand-icon"><Scale size={25} /></span><span>Ghana Legal<strong>Workspace</strong></span></a>
      <span className="workspace-label">LEGAL & COMPLIANCE</span>
      <nav aria-label="Main navigation">{navigation.map(({ id, label, icon: Icon }) => <button key={id} disabled={!!busy} className={`nav-item ${page === id ? 'active' : ''}`} aria-current={page === id ? 'page' : undefined} onClick={() => navigate(id)}><Icon size={19} />{label}{id === 'documents' && documents.length > 0 && <span className="nav-count">{documents.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="ghana-mark"><i /><i /><i /></div><strong>Ghana jurisdiction</strong><span>AI Compliance Platform</span><small>Local workspace / v0.1</small></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" title="Toggle navigation" aria-label="Toggle navigation" onClick={() => setMobileNav(!mobileNav)}><Menu size={21} /></button><span>Workspace</span><ChevronRight size={14} /><strong>{pageTitle}</strong></div><div className="connection"><span className={`status-dot ${health ? 'online' : ''}`} />{loading ? 'Connecting' : health ? (health.ai_configured ? 'AI connected' : 'Search ready / AI not configured') : 'Offline'}<button className="icon-button" aria-label="Refresh workspace" title="Refresh workspace" disabled={loading || !!busy} onClick={() => void reload()}><RefreshCw size={16} className={loading ? 'spin' : ''} /></button></div></header>
      <main>
        {error && <div className="alert" role="alert"><CircleAlert size={18} />{error}</div>}
        {notice && <div className="notice" role="status"><Check size={17} />{notice}<button className="icon-button" aria-label="Dismiss notification" title="Dismiss" onClick={() => setNotice('')}><X size={16} /></button></div>}
        <div className="page-heading"><div><span className="eyebrow">GHANA LEGAL WORKSPACE</span><h1>{page === 'dashboard' ? 'Workspace overview' : pageTitle}</h1><p>{({ dashboard: 'Matters, authorities and recent work.', research: 'Judgments, statutes and matter documents.', analysis: 'Case facts, relevant authorities and possible legal approaches.', documents: 'Shared authorities and private matter files.', matters: 'Case files and ongoing legal work.', reports: 'Saved research and case analyses.' })[page]}</p></div><div className="heading-actions">{page === 'matters' ? <button disabled={!health} onClick={() => { setMatterError(''); setModal('matter'); }}><Plus size={17} />New matter</button> : uploadButton}</div></div>

        {page === 'dashboard' && <>
          <div className="metrics">{[
            ['Active matters', dashboard?.matters, FolderOpen, 'matters'],
            ['Matter documents', dashboard?.matter_documents, FileText, 'documents'],
            ['Library authorities', dashboard ? dashboard.judgments + dashboard.statutes : undefined, BookOpen, 'documents'],
            ['Saved reports', dashboard?.reports, FileSearch, 'reports'],
          ].map(([label, value, Icon, target]) => {
            const MetricIcon = Icon as typeof FolderOpen;
            return <button className="metric" key={String(label)} onClick={() => { if (target === 'documents') setFilter(label === 'Matter documents' ? 'matter' : 'library'); navigate(target as Page); }}><span>{String(label)}<MetricIcon size={18} /></span><strong>{typeof value === 'number' ? value : '\u2014'}</strong><small>View records <ArrowRight size={14} /></small></button>;
          })}</div>
          <div className="overview-grid"><section><div className="section-heading"><h2>Recent documents</h2><button className="text-link" onClick={() => navigate('documents')}>View all <ArrowRight size={15} /></button></div>
            {dashboard?.recent_documents.length ? <div className="document-list">{dashboard.recent_documents.map(d => <a className="document-row" key={d.id} href={documentUrl(d.id)}><span className="file-icon"><FileText size={21} /></span><div><strong>{d.title}</strong><small>{kindLabel(d.kind)} / {date(d.created_at)}</small></div><ArrowDownToLine size={16} /></a>)}</div> : <Empty icon={<BookOpen size={33} />} title="No documents yet" action={uploadButton} />}
          </section><section className="library-overview"><div className="section-heading"><h2>Legal library</h2><Gavel size={20} /></div><div className="library-count"><strong>{dashboard ? dashboard.judgments : '\u2014'}</strong><span>Judgments</span></div><div className="library-count"><strong>{dashboard ? dashboard.statutes : '\u2014'}</strong><span>Statutes</span></div><p className="muted">{dashboard?.library_updated_at ? `Last added ${date(dashboard.library_updated_at)}` : 'No authorities indexed'}</p><span className="tag neutral">Uploaded sources only</span><div className="section-actions"><button className="secondary" onClick={() => navigate('research')}><Search size={16} />Open research</button></div></section></div>
          <section className="recent-work"><div className="section-heading"><h2>Recent research & analyses</h2><button className="text-link" onClick={() => navigate('reports')}>All reports <ArrowRight size={15} /></button></div>{dashboard?.recent_reports.length ? dashboard.recent_reports.map(r => <button className="report-row" key={r.id} onClick={() => openReport(r)}><FileSearch size={19} /><div><strong>{r.payload.title}</strong><small>{date(r.created_at)}</small></div><ChevronRight size={18} /></button>) : <Empty icon={<FileSearch size={30} />} title="No saved reports" action={<button className="secondary" onClick={() => navigate('research')}><Search size={16} />Start research</button>} />}</section>
        </>}

        {page === 'documents' && <>
          <div className="toolbar"><div className="segmented" role="group" aria-label="Document collection"><button className={filter === 'library' ? 'selected' : ''} onClick={() => setFilter('library')}>Legal library</button><button className={filter === 'matter' ? 'selected' : ''} onClick={() => setFilter('matter')}>Matter files</button></div><div className="toolbar-fields">{filter === 'matter' && matterSelect()}<label className="search-field"><Search size={17} /><input value={documentQuery} onChange={e => setDocumentQuery(e.target.value)} aria-label="Filter documents" placeholder="Find a document" /></label></div></div>
          {filteredDocs.length ? <DocumentTable documents={filteredDocs} matters={matters} /> : <Empty icon={<BookOpen size={34} />} title={documentQuery ? 'No matching documents' : 'No documents in this collection'} action={uploadButton} />}
        </>}

        {page === 'matters' && <>{matters.length ? <div className="table-wrap"><table><thead><tr><th>Matter</th><th>Reference</th><th>Documents</th><th>Created</th><th /></tr></thead><tbody>{matters.map(m => <tr key={m.id}><td><strong>{m.name}</strong>{m.description && <small>{m.description}</small>}</td><td>{m.reference || '\u2014'}</td><td>{m.document_count}</td><td className="nowrap">{date(m.created_at)}</td><td><button className="text-link" onClick={() => { changeMatter(m.id); setFilter('matter'); navigate('documents'); }}>Open <ArrowRight size={15} /></button></td></tr>)}</tbody></table></div> : <Empty icon={<FolderOpen size={36} />} title="No matters yet" action={<button disabled={!health} onClick={() => setModal('matter')}><Plus size={16} />New matter</button>} />}</>}

        {page === 'research' && <>
          <form onSubmit={research} className="research-form"><div className="form-grid"><label>Collection<select value={scope} disabled={!!busy} onChange={e => { setScope(e.target.value); setResults(null); setReport(null); }}><option value="library">Legal library</option><option value="matter">Matter documents</option><option value="both">Library + selected matter</option></select></label>{scope !== 'library' && <label>Matter{matterSelect(true)}</label>}</div>
            <label>Research question<textarea value={query} disabled={!!busy} onChange={e => setQuery(e.target.value)} required minLength={3} maxLength={3000} placeholder="e.g. What authorities address termination for breach of contract?" /></label>
            <div className="form-actions"><button type="submit" name="mode" value="search" disabled={!!busy || !health}><Search size={17} />Search passages</button><button type="submit" name="mode" value="answer" className="secondary" disabled={!!busy || !health?.ai_configured} title={health?.ai_configured ? 'Generate a cited answer' : 'AI connection required'}><FileSearch size={17} />Generate cited answer</button>{busy && <LoaderCircle className="spin" size={18} />}</div>
          </form>
          {actionError && <div className="alert" role="alert">{actionError}</div>}
          {results && <section className="search-results"><div className="section-heading"><h2>Source passages</h2><span className="muted">{results.length} matches / keyword ranking</span></div>{results.length ? results.map(s => <article className="search-result" key={s.chunk_id}><div className="result-meta"><span className="tag">{kindLabel(s.kind)}</span><span>{s.locator}</span></div><button className="result-title" onClick={() => setSource(s)}>{s.title}<ArrowRight size={17} /></button><p className="muted">{[s.citation, s.court].filter(Boolean).join(' / ')}</p><p className="passage-preview">{s.text}</p><button className="text-link" onClick={() => setSource(s)}>View source passage <ChevronRight size={15} /></button></article>) : <Empty icon={<Search size={32} />} title="No matching passages" />}</section>}
          {report && <Report report={report} openSource={setSource} onVerified={verifiedReport} onVerifyBusy={setBusy} />}
        </>}

        {page === 'analysis' && <>
          {!advancedAnalysis && <>
          <div className="analysis-matter"><label>Case matter<select aria-label="Case matter" value={matterId} disabled={!!busy} onChange={e => changeMatter(e.target.value)}><option value="">Select a matter</option>{matters.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label><button className="secondary" disabled={!!busy} onClick={() => setModal('matter')}><Plus size={16} />New matter</button><button className="secondary" disabled={!matterId || !!busy} onClick={() => setModal('upload')}><Upload size={16} />Upload case</button></div>
          <CaseWorkflow key={matterId} matterId={matterId} documents={documents.filter(d => d.kind === 'matter' && d.matter_id === matterId)} aiConfigured={!!health?.ai_configured} busy={!!busy} onBusy={setBusy} onReport={item => { setReport(item); if (item) void reload(); }} />
          </>}
          <details className="advanced-analysis" onToggle={e => setAdvancedAnalysis(e.currentTarget.open)}><summary onClick={e => { if (busy) e.preventDefault(); }}>Advanced evidence review</summary>
          <div className="toolbar"><div className="segmented" role="group" aria-label="Analysis mode"><button disabled={!!busy} className={analysisMode === 'termination' ? 'selected' : ''} aria-pressed={analysisMode === 'termination'} onClick={() => { setAnalysisMode('termination'); setReport(null); }}>Termination &amp; Cure</button><button disabled={!!busy} className={analysisMode === 'general' ? 'selected' : ''} aria-pressed={analysisMode === 'general'} onClick={() => { setAnalysisMode('general'); setReport(null); }}>General Analysis</button></div></div>
          {analysisMode === 'termination' ? <>
            <div className="analysis-matter"><label>Matter{matterSelect(true)}</label><button className="secondary" disabled={!matterId || !!busy || !health?.ai_configured} onClick={() => void prepareBrief()}><FileSearch size={16} />Extract proposed brief</button></div>
            {brief?.truncated && <div className="alert" role="alert">The proposed brief covers only part of the case file. Review all original documents.</div>}
            {brief?.fact_excerpts && <details className="brief-notes"><summary>Case-document excerpts in the proposed brief</summary><p className="muted">{brief.warning}</p>{brief.fact_excerpts.map(unit => {
              const source = brief.sources.find(s => s.chunk_id === unit.source_id);
              return <div key={unit.id}><blockquote className="supporting-quote">{unit.text}</blockquote>{source && <button className="citation" onClick={() => setSource(source)}><BookOpen size={13} />{source.title} / {source.locator}</button>}</div>;
            })}</details>}
            <TerminationReview key={matterId} matterId={matterId} facts={facts} onFactsChange={text => { setFacts(text); setConfirmed(false); }} busy={!!busy} aiConfigured={!!health?.ai_configured} onBusy={setBusy} onReport={item => { setReport(item); if (item) void reload(); }} openSource={setSource} />
            {actionError && <div className="alert" role="alert">{actionError}</div>}
          </> : <>
          <div className="alert" role="alert">General Analysis is paused. Use Termination &amp; Cure for new claim-level drafts. Existing reports remain available in Reports.</div>
          <div className="analysis-steps"><span className="current">01 Case file</span><ChevronRight size={14} /><span className={facts ? 'current' : ''}>02 Confirm facts & issues</span><ChevronRight size={14} /><span className={report ? 'current' : ''}>03 Authority analysis</span></div>
          <div className="analysis-matter"><label>Matter{matterSelect(true)}</label><button className="secondary" onClick={() => void prepareBrief()} disabled={!matterId || !health?.ai_configured || !!busy}>{busy === 'brief' ? <LoaderCircle className="spin" size={16} /> : <FileSearch size={16} />}Extract proposed brief</button></div>
          {selectedMatter && <div className="matter-summary"><FolderOpen size={19} /><strong>{selectedMatter.name}</strong><span>{selectedMatter.document_count} documents</span><button className="text-link" onClick={() => { setFilter('matter'); navigate('documents'); }}>View files <ArrowRight size={14} /></button></div>}
          <form className="case-form" onSubmit={analyze}>
            <label>Case facts<textarea value={facts} disabled={!!busy} minLength={10} maxLength={12000} required onChange={e => { setFacts(e.target.value); setConfirmed(false); setReport(null); }} placeholder="Case facts for review" /></label>
            <label>Legal issues<textarea value={issues} disabled={!!busy} required onChange={e => { setIssues(e.target.value); setConfirmed(false); setReport(null); }} placeholder="One issue per line" /></label>
            {brief && <div className="brief-notes">{brief.truncated && <p className="alert">The proposed brief covers only part of the case file. Review all original documents.</p>}{brief.missing_information.length > 0 && <><h3>Missing information</h3><ul>{brief.missing_information.map((text, i) => <li key={i}>{text}</li>)}</ul></>}<details><summary>Case passages considered ({brief.sources.length})</summary>{brief.sources.map(s => <button type="button" className="citation" key={s.chunk_id} onClick={() => setSource(s)}>{s.title} / {s.locator}</button>)}</details></div>}
            <label className="checkbox"><input type="checkbox" checked={confirmed} disabled={!!busy} required onChange={e => setConfirmed(e.target.checked)} />I have reviewed and confirmed the facts and legal issues.</label>
            <div className="form-actions"><button disabled type="submit"><Scale size={17} />Analyse relevant authorities</button><span className="muted">Paused pending claim-level review</span></div>
          </form>
          {actionError && <div className="alert" role="alert">{actionError}</div>}
          </>}
          </details>
          {report && <Report report={report} openSource={setSource} onVerified={verifiedReport} onVerifyBusy={setBusy} />}
        </>}

        {page === 'reports' && <>{report ? <><button disabled={!!busy} className="text-link back-link" onClick={() => setReport(null)}>All reports</button><Report report={report} openSource={setSource} onVerified={verifiedReport} onVerifyBusy={setBusy} /></> : reports.length ? <div className="report-list">{reports.map(r => <button className="report-row" key={r.id} onClick={() => setReport(r)}><FileSearch size={21} /><div><strong>{r.payload.title}</strong><small>{r.kind === 'research' ? 'Legal research' : 'Case analysis'} / {date(r.created_at)}{r.matter_id ? ` / ${matters.find(m => m.id === r.matter_id)?.name || 'Matter'}` : ''}</small></div><ChevronRight size={18} /></button>)}</div> : <Empty icon={<FileText size={34} />} title="No saved reports" action={<button className="secondary" onClick={() => navigate('research')}><Search size={16} />Start research</button>} />}</>}
      </main>
      <footer>Ghana Legal Workspace<span>AI Compliance Platform / Local prototype</span></footer>
    </div>
    {modal === 'upload' && <Modal title="Upload document" close={() => setModal(null)}><UploadForm matters={matters} initialMatter={matterId} initialKind={page === 'analysis' ? 'matter' : 'judgment'} onDone={() => { setModal(null); setNotice('Document indexed and ready to search.'); void reload(); }} /></Modal>}
    {modal === 'matter' && <Modal title="New matter" close={() => { if (!busy) setModal(null); }}><form className="form-stack" onSubmit={createMatter}><label>Matter name<input name="name" required maxLength={160} autoFocus /></label><label>Reference<input name="reference" maxLength={80} /></label><label>Description<textarea name="description" maxLength={3000} /></label>{matterError && <div className="alert" role="alert">{matterError}</div>}<div className="modal-footer"><button disabled={!!busy} type="submit"><Plus size={16} />Create matter</button></div></form></Modal>}
    {source && <SourceView source={source} close={() => setSource(null)} />}
  </div>;
}
