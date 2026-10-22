import { test, expect } from '@playwright/test';

function fixture(matterId) {
  const texts = {
    receipt: "A courier record shows delivery at ECS's office on 12 August.",
    access: 'ECS proposed a repair visit for 20 August. EHL offered access after 5 p.m. or on 24 August. The email chain does not establish whether either alternative was agreed.',
    attribution: 'ECS questions the logger calibration and says power interruptions caused the excursions.',
    certificate: 'Neither party has produced an acceptance certificate signed by EHL.',
  };
  const source = (chunk_id, kind, text, title) => ({ chunk_id, document_id: `workflow-${chunk_id}`, kind, text, title,
    citation: kind === 'judgment' ? 'SYNTHETIC AUTHORITY' : '', locator: 'Page 3', filename: 'test.txt', court: '', decision_date: '', source_url: '' });
  const caseSource = source(133, 'matter', Object.values(texts).join(' '), 'Fictional EHL ECS case');
  const contract = source(131, 'matter', 'Written notice must allow fourteen days after receipt. Reasonable access is required.', 'Fictional agreement');
  const authority = source(110, 'judgment', 'The court examined the express notice condition in that earlier agreement.', 'Synthetic test judgment');
  const spans = [{ role: 'facts', source_id: 133, text: texts.receipt, start: 0, end: texts.receipt.length },
    { role: 'contract', source_id: 131, text: contract.text, start: 0, end: contract.text.length },
    { role: 'authority', source_id: 110, text: authority.text, start: 0, end: authority.text.length }];
  const claims = [
    { id: 'I1C1', scope: 'general_principle', report_kind: 'reasoning', text: authority.text, wording_origin: 'source_text',
      evidence_check: 'matched', semantic_status: 'supported', check_issues: [], spans: [spans[2]] },
    ...['similarity', 'difference', 'argument_for_termination', 'argument_against_termination', 'weakness'].map((kind, i) => ({
      id: `I1C${i + 2}`, scope: 'comparison', report_kind: kind, text: ({
        similarity: 'Both reviewed excerpts concern an express notice condition; compliance in this case remains unresolved.',
        difference: 'The current case records a disputed repair arrangement that the quoted reasoning does not resolve.',
        argument_for_termination: 'The party seeking termination could rely on the documented notice, subject to the remaining contractual conditions.',
        argument_against_termination: 'The party resisting termination could dispute remedial access, subject to review of the correspondence.',
        weakness: 'EHL will certainly win and damages are guaranteed.',
      })[kind], evidence_check: 'matched', semantic_status: kind === 'weakness' ? 'insufficient_evidence' : 'not_checked', check_issues: [], spans,
      verification: { origin: kind === 'weakness' ? 'model' : 'policy_gate', model_verdict: kind === 'weakness' ? 'insufficient_evidence' : 'supported',
        reason: 'Synthetic assessment only; lawyer review remains required.', evidence: spans },
    })),
  ];
  return { id: 'workflow-report', kind: 'case_analysis', matter_id: matterId, query: 'Termination and cure', created_at: new Date().toISOString(), payload: {
    title: 'Termination and cure - case analysis', workflow: 'case_workflow_v1', claims, findings: [],
    scope: 'Termination and cure only. Other case issues have not been analysed.', warning: 'Unverified AI draft for lawyer review.',
    sources: [caseSource, contract, authority], limitations: ['Synthetic browser fixture, not legal validation.'],
    brief: { facts: Object.values(texts).join('\n'), issues: ['Termination and cure'], missing_information: [], truncated: true, sources: [caseSource],
      fact_excerpts: Object.values(texts).map((text, i) => ({ id: `fact-${i}`, text, source_id: 133, start: 0, end: text.length })) },
    issue_reports: [
      { key: 'notice_and_cure', title: 'Written notice and opportunity to remedy', claims, sources: [contract, authority], notes: [], coverage: { assessed: 2, candidates: 4, issue_units_selected: 4, issue_units_available: 8 } },
      { key: 'remedial_access', title: 'Access for remedial work', claims: [], sources: [], notes: ['No source-supported application was established for this issue.'] },
      { key: 'material_breach', title: 'Alleged material breach and termination', claims: [], sources: [], notes: ['The selected authority does not establish a materiality test for this dispute.'] },
    ],
  } };
}

async function setup(page, request, name) {
  const matter = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name } })).json();
  await request.post('http://127.0.0.1:8012/api/documents', { multipart: {
    kind: 'matter', matter_id: matter.id, permission_confirmed: 'true', title: 'Fictional cold-storage dispute',
    file: { name: 'case.txt', mimeType: 'text/plain', buffer: Buffer.from('Fictional case: notice, receipt, repair access and disputed material breach.') },
  } });
  await page.route('**/api/health', route => route.fulfill({ json: { service: 'Ghana Legal Workspace', ai_configured: true, model: 'synthetic-test' } }));
  return matter;
}

test('one Analyze Case action leads to six sourced sections, with unsafe text withheld', async ({ page, request }, testInfo) => {
  const matter = await setup(page, request, 'One-action EHL ECS browser test');
  const report = fixture(matter.id);
  let starts = 0; let polls = 0;
  const job = { id: 'one-action-job', matter_id: matter.id, status: 'queued', stage: 'brief', progress: 10,
    message: 'Identifying facts and legal issues', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), retry_at: null, report_id: null, report: null };
  await page.route('**/api/case-analysis/jobs?*', route => route.fulfill({ json: [] }));
  await page.route('**/api/case-analysis/jobs', route => {
    starts += 1; expect(route.request().postDataJSON()).toEqual({ matter_id: matter.id });
    return route.fulfill({ status: 202, json: job });
  });
  await page.route('**/api/case-analysis/jobs/one-action-job', route => {
    polls += 1;
    return route.fulfill({ json: polls === 1 ? { ...job, status: 'running', progress: 45, message: 'Checking evidence: written notice' }
      : { ...job, status: 'completed', progress: 100, message: 'Draft report ready for lawyer review.', report_id: report.id, report } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByLabel('Case matter', { exact: true }).selectOption(matter.id);
  await page.getByRole('button', { name: 'Upload case', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('combobox', { name: 'Collection', exact: true })).toHaveValue('matter');
  await expect(page.getByRole('dialog').getByRole('combobox', { name: 'Matter', exact: true })).toHaveValue(matter.id);
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Case facts', exact: true })).not.toBeVisible();
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await page.getByRole('button', { name: 'Analyze Case', exact: true }).click();
  await expect(page.getByRole('progressbar', { name: 'Case analysis progress' })).toBeVisible();
  await expect(page.getByRole('heading', { name: report.payload.title, exact: true })).toBeVisible();
  for (const title of ['Case Summary', 'Legal Issues', 'Relevant Judgments', 'How They Apply', 'Arguments and Weaknesses', 'Missing Evidence']) {
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  }
  const summary = page.getByRole('region', { name: 'Case Summary', exact: true });
  await expect(summary).toContainText('12 August'); await expect(summary).toContainText('24 August');
  await expect(summary).toContainText('ECS questions'); await expect(summary).toContainText('Neither party has produced');
  await expect(page.getByRole('region', { name: 'Arguments and Weaknesses', exact: true })).toContainText('party resisting termination could dispute remedial access');
  await expect(page.getByText('EHL will certainly win and damages are guaranteed.', { exact: true })).not.toBeVisible();
  await expect(page.getByRole('region', { name: 'Missing Evidence', exact: true })).toContainText('materiality test');
  expect(starts).toBe(1);
  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('one-action-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('one-action-mobile.png'), fullPage: true });
  await summary.getByRole('button', { name: 'Fictional EHL ECS case / Page 3', exact: true }).first().click();
  await expect(page.getByRole('dialog')).toContainText('12 August');
});

test('paused work survives reload and resumes explicitly without another Analyze request', async ({ page, request }) => {
  const matter = await setup(page, request, 'Persisted case-analysis browser test');
  let starts = 0; let resumes = 0;
  let job = { id: 'paused-job', matter_id: matter.id, status: 'paused', stage: 'roles:notice_and_cure', progress: 25,
    message: 'Provider rate limit reached. Completed steps are saved.', retry_at: new Date(Date.now() + 2000).toISOString(),
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(), report_id: null, report: null };
  await page.route('**/api/case-analysis/jobs?*', route => route.fulfill({ json: [job] }));
  await page.route('**/api/case-analysis/jobs', route => { starts += 1; return route.abort(); });
  await page.route('**/api/case-analysis/jobs/paused-job/resume', route => {
    resumes += 1; job = { ...job, status: 'queued', retry_at: null, message: 'Resuming saved analysis steps.' };
    return route.fulfill({ status: 202, json: job });
  });
  await page.route('**/api/case-analysis/jobs/paused-job', route => route.fulfill({ json: {
    ...job, status: 'completed', progress: 100, message: 'Draft report ready for lawyer review.', report_id: 'workflow-report', report: fixture(matter.id),
  } }));
  await page.goto('/'); await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByLabel('Case matter', { exact: true }).selectOption(matter.id);
  await expect(page.getByRole('status')).toContainText('Completed steps are saved');
  await page.reload(); await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByLabel('Case matter', { exact: true }).selectOption(matter.id);
  await expect(page.getByRole('button', { name: 'Resume analysis', exact: true })).toBeEnabled({ timeout: 8000 });
  expect(starts).toBe(0); expect(resumes).toBe(0);
  await page.getByRole('button', { name: 'Resume analysis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Arguments and Weaknesses', exact: true })).toBeVisible();
  expect(starts).toBe(0); expect(resumes).toBe(1);
});
