import { test, expect } from '@playwright/test';

test('document-grounded report exposes receipt and repair evidence without verifying an entered summary', async ({ page }, testInfo) => {
  const receipt = "A courier record shows delivery at ECS's office on 12 August.";
  const access = 'ECS proposed a repair visit for 20 August. EHL offered entry after 5 p.m. or on 24 August. The email chain does not establish agreement.';
  const power = 'ECS questions the logger calibration and says power interruptions caused the excursions.';
  const certificate = 'Neither party has produced an acceptance certificate signed by EHL.';
  const text = [receipt, access, power, certificate].join(' ');
  const source = { chunk_id: 133, document_id: 'synthetic-case', kind: 'matter', text, title: 'Synthetic case chronology',
    citation: '', locator: 'Page 3', filename: 'test.txt', court: '', decision_date: '', source_url: '' };
  const units = [receipt, access, power, certificate].map((text, i) => ({ id: `case_${i}`, source_id: 133, text, start: 0, end: text.length }));
  const factSpan = { role: 'facts', source_id: 133, text: power, start: 0, end: power.length };
  const claims = [{ id: 'C1', scope: 'case_fact', text: power, factual_origin: 'case_document', wording_origin: 'source_text',
    spans: [factSpan], evidence_check: 'matched', check_issues: [], semantic_status: 'supported' },
    ...['notice_and_cure', 'remedial_access', 'material_breach'].map((topic, i) => ({ id: `C${i + 2}`, scope: 'not_established',
      application_topic: topic, application_alignment: 'evidence_gap', wording_origin: 'review_question',
      text: 'What does the reviewed evidence establish for this issue?', spans: [], evidence_check: 'no_evidence', check_issues: [], semantic_status: 'insufficient_evidence' }))];
  await page.route('**/api/reports', route => route.fulfill({ json: [{ id: 'source-grounded', kind: 'case_analysis', matter_id: null,
    query: 'Termination', created_at: new Date().toISOString(), payload: { title: 'Document-grounding regression', workflow: 'termination_atomic_v2',
      claims, findings: [], limitations: [], sources: [source], confirmed_facts: 'EHL admits power interruptions. No certificate was signed.',
      case_evidence: { version: 'document_facts_v1', text, units, sources: [source], topics: {
        notice_and_cure: ['case_0'], remedial_access: ['case_1'], material_breach: ['case_2', 'case_3'] },
        coverage: { passages_considered: 1, units_considered: 4, units_selected: 4, incomplete: true },
        warning: 'Case-document excerpts are not independently proven facts. The entered summary is not used as documentary proof.' } } }] }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: /Document-grounding regression/ }).click();
  const readable = page.locator('.readable-report');
  await expect(readable).toContainText('document wording - not factual proof');
  await expect(readable).not.toContainText('EHL admits');
  await expect(readable).not.toContainText('No certificate was signed');
  await expect(readable).toContainText('not a full-file review');
  await expect(page.locator('[data-report-claim-id=C2]')).toContainText(receipt);
  await expect(page.locator('[data-report-claim-id=C3]')).toContainText(access);
  await expect(page.locator('[data-report-claim-id=C4]')).toContainText(certificate);
  await page.setViewportSize({ width: 1440, height: 1000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('document-grounding-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('document-grounding-mobile.png'), fullPage: true });
  await page.locator('[data-report-claim-id=C3]').getByRole('button', { name: 'Synthetic case chronology / Page 3', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText(receipt);
});

test('desktop: create matter, upload authority, search, inspect source and original', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByText('Search ready / AI not configured')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('desktop-overview.png'), fullPage: true });
  await page.getByRole('button', { name: 'Matters', exact: true }).click();
  await page.getByRole('button', { name: 'New matter' }).first().click();
  await page.getByLabel('Matter name', { exact: true }).fill('Synthetic browser test matter');
  await page.getByRole('button', { name: 'Create matter' }).click();
  await expect(page.getByText('Matter created.')).toBeVisible();
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: /^Documents/ }).click();
  await page.getByRole('button', { name: 'Upload document' }).first().click();
  await page.locator('input[type=file]').setInputFiles({ name: 'synthetic-authority.txt', mimeType: 'text/plain', buffer: Buffer.from('SYNTHETIC TEST AUTHORITY - NOT REAL CASE LAW.\n\nThis test passage discusses breach of contract and termination notice.') });
  await page.getByLabel('Document title').fill('Synthetic test authority');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Upload document', exact: true }).last().click();
  await expect(page.getByText('Document indexed and ready to search.')).toBeVisible();
  await page.getByRole('button', { name: 'Legal Research', exact: true }).click();
  await page.getByLabel('Research question').fill('contract termination notice');
  await page.getByRole('button', { name: 'Search passages' }).click();
  await expect(page.getByRole('button', { name: 'Synthetic test authority', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'View source passage' }).first().click();
  await expect(page.getByRole('dialog')).toContainText('Paragraph 2');
  await expect(page.getByRole('dialog')).toContainText('termination notice');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Original document' }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('synthetic-authority.txt');
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('desktop-research.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('mobile: navigation, upload dialog, and case confirmation fit the viewport', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Workspace overview' })).toBeVisible();
  await expect(page.getByText('Search ready / AI not configured')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('mobile-overview.png'), fullPage: true });
  await page.getByRole('button', { name: 'Toggle navigation' }).click();
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Case Analysis', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Analyze Case', exact: true })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('mobile-case-analysis.png'), fullPage: true });
  await page.getByRole('button', { name: 'Upload document' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  const dialog = await page.getByRole('dialog').boundingBox();
  expect(dialog.x).toBeGreaterThanOrEqual(0);
  expect(dialog.x + dialog.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: testInfo.outputPath('mobile-upload.png'), fullPage: true });
});

test('legacy analysis is paused while saved reports and citations remain readable', async ({ page, request }, testInfo) => {
  const matter = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name: 'Synthetic analysis matter' } })).json();
  await page.route('**/api/health', route => route.fulfill({ json: { ai_configured: true, model: 'test-model' } }));
  await page.route('**/api/case-analysis/brief', route => route.fulfill({ json: {
    facts: 'Proposed synthetic facts for lawyer review.', issues: ['Contract breach'],
    missing_information: ['Confirm service of notice.'], sources: [], truncated: true,
  } }));
  await page.route('**/api/reports', async route => {
    await route.fulfill({ json: [{
      id: 'synthetic-report', kind: 'case_analysis', matter_id: matter.id, created_at: new Date().toISOString(), query: 'Contract termination',
      payload: { title: 'Synthetic authority comparison', grounding_version: 1, findings: [{ category: 'comparison', text: 'Test comparison only.', source_ids: [55, 56], supporting_quotes: [{ source_id: 55, quote: 'Exact synthetic supporting passage.' }] }],
        limitations: ['Synthetic browser test, not legal advice.'], sources: [{ chunk_id: 55, document_id: 'test-id',
          title: 'Synthetic test authority', filename: 'test.txt', kind: 'judgment', locator: 'Paragraph 2',
          text: 'Exact synthetic supporting passage.', citation: 'TEST ONLY', court: '', decision_date: '', source_url: '' },
          { chunk_id: 56, document_id: 'case-id', title: 'Uploaded fictional case', filename: 'case.txt', kind: 'matter', locator: 'Page 2',
            text: 'Exact synthetic case-file evidence.', citation: '', court: '', decision_date: '', source_url: '' }] },
    }] });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByText('Advanced evidence review', { exact: true }).click();
  await page.getByRole('button', { name: 'General Analysis', exact: true }).click();
  await page.getByLabel('Matter', { exact: true }).selectOption(matter.id);
  await page.getByRole('button', { name: 'Extract proposed brief' }).click();
  await expect(page.getByLabel('Case facts')).toHaveValue('Proposed synthetic facts for lawyer review.');
  await expect(page.getByText('The proposed brief covers only part of the case file. Review all original documents.')).toBeVisible();
  await page.getByLabel('Case facts').fill('Lawyer corrected synthetic facts.');
  await page.getByRole('textbox', { name: 'Legal issues', exact: true }).fill('Contract termination');
  await expect(page.getByRole('button', { name: 'Analyse relevant authorities' })).toBeDisabled();
  await page.getByRole('checkbox').check();
  await expect(page.getByRole('button', { name: 'Analyse relevant authorities' })).toBeDisabled();
  const paused = await request.post('http://127.0.0.1:8012/api/case-analysis', { data: { matter_id: matter.id, facts: 'Synthetic facts for a paused workflow.', issues: ['Termination'], confirmed: true } });
  expect(paused.status()).toBe(409);
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: /Synthetic authority comparison/ }).click();
  await expect(page.getByRole('heading', { name: 'Synthetic authority comparison' })).toBeVisible();
  await expect(page.getByRole('alert').filter({ hasText: 'AI-generated draft.' })).toBeVisible();
  await expect(page.getByRole('alert').filter({ hasText: 'Legacy paragraph-format report.' })).toBeVisible();
  await expect(page.getByText('Authority comparison', { exact: true })).toBeVisible();
  await expect(page.locator('.supporting-quote')).toContainText('Exact synthetic supporting passage.');
  await page.screenshot({ path: testInfo.outputPath('case-report.png'), fullPage: true });
  await page.getByRole('button', { name: 'TEST ONLY / Paragraph 2' }).click();
  await expect(page.getByRole('dialog')).toContainText('Exact synthetic supporting passage.');
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await page.getByRole('button', { name: 'Case file: Uploaded fictional case / Page 2' }).click();
  await expect(page.getByRole('dialog')).toContainText('Exact synthetic case-file evidence.');
});

test('focused termination: reviewed quotations, confirmation reset, report evidence and mobile layout', async ({ page, request }, testInfo) => {
  const matter = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name: 'Synthetic focused termination matter' } })).json();
  const clause = "\u{1F4C4} SYNTHETIC CONTRACT. Written notice must identify the breach and allow fourteen days after receipt to remedy it before termination. Reasonable remedial access is required.";
  const reasoning = 'SYNTHETIC TEST AUTHORITY, NOT REAL LAW. A contractual termination clause states the conditions for ending the agreement.';
  async function upload(text, kind, name) {
    const document = await (await request.post('http://127.0.0.1:8012/api/documents', { multipart: {
      kind, matter_id: kind === 'matter' ? matter.id : '', permission_confirmed: 'true', title: name,
      file: { name: `${kind}-review.txt`, mimeType: 'text/plain', buffer: Buffer.from(text) },
    } })).json();
    const sources = await (await request.post('http://127.0.0.1:8012/api/search', { data: { query: 'termination', scope: kind === 'matter' ? 'matter' : 'library', matter_id: kind === 'matter' ? matter.id : null } })).json();
    return sources.find(s => s.document_id === document.id);
  }
  const contract = await upload(clause, 'matter', 'Synthetic reviewed agreement');
  const authority = await upload(reasoning, 'judgment', 'Synthetic reviewed reasoning');
  let draftReport;
  let generationCalls = 0;
  let verificationCalls = 0;
  await page.route('**/api/health', route => route.fulfill({ json: { ai_configured: true, model: 'test-model' } }));
  await page.route('**/api/case-analysis/termination', async route => {
    generationCalls += 1;
    const body = route.request().postDataJSON();
    expect(body.contract).toEqual({ source_id: contract.chunk_id, quote: clause });
    expect(body.authority).toEqual({ source_id: authority.chunk_id, quote: reasoning });
    expect(body.confirmed).toBe(true); expect(body.reasoning_confirmed).toBe(true);
    const spanText = 'fourteen days after receipt';
    const start = Array.from(clause.slice(0, clause.indexOf(spanText))).length;
    draftReport = { id: 'focused-synthetic-report', kind: 'case_analysis', matter_id: matter.id,
      query: 'Termination and cure', created_at: new Date().toISOString(), payload: {
        title: 'Termination and cure - atomic evidence review', workflow: 'termination_atomic_v2', grounding_version: 2,
        reviewed_evidence: { contract: body.contract, authority: body.authority },
        evidence_texts: { contract: clause, authority: reasoning, facts: body.facts },
        claims: [
          { id: 'C1', scope: 'contract_term', text: 'The contract specifies fourteen days after receipt.', evidence_check: 'matched', semantic_status: 'not_checked', check_issues: [],
            spans: [{ role: 'contract', text: spanText, start, end: start + Array.from(spanText).length, source_id: contract.chunk_id }] },
          { id: 'C2', scope: 'comparison', text: 'SYNTHETIC FLAGGED CLAIM: The contract is therefore enforceable.', evidence_check: 'flagged', semantic_status: 'not_checked', check_issues: ['missing_required_role'], spans: [] },
          { id: 'C3', scope: 'not_established', text: 'Was reasonable remedial access provided?', evidence_check: 'no_evidence', semantic_status: 'not_checked', check_issues: [], spans: [] },
          { id: 'C4', scope: 'contract_term', text: 'SYNTHETIC CONTRADICTED CLAIM: The contract requires seven days after receipt.', evidence_check: 'matched', semantic_status: 'not_checked', check_issues: [],
            spans: [{ role: 'contract', text: spanText, start, end: start + Array.from(spanText).length, source_id: contract.chunk_id }] },
          { id: 'C5', scope: 'comparison', text: 'SYNTHETIC INFERENCE: The cure period is legally consistent with the judgment.', evidence_check: 'matched', semantic_status: 'not_checked', check_issues: [],
            spans: [{ role: 'contract', text: spanText, start, end: start + Array.from(spanText).length, source_id: contract.chunk_id },
                    { role: 'authority', text: reasoning, start: 0, end: Array.from(reasoning).length, source_id: authority.chunk_id }] },
        ],
        confirmed_facts: body.facts, confirmed_issues: ['Termination and cure'],
        findings: [],
        sources: [contract, authority], limitations: ['Synthetic test only. Lawyer review required.'],
      } };
    await route.fulfill({ json: draftReport });
  });
  await page.route('**/api/reports/focused-synthetic-report/verify', async route => {
    verificationCalls += 1;
    expect(route.request().method()).toBe('POST');
    if (verificationCalls === 1) {
      await route.fulfill({ status: 503, json: { detail: 'Verifier temporarily unavailable.' } });
      return;
    }
    const result = JSON.parse(JSON.stringify(draftReport)); result.id = 'verified-synthetic-report';
    result.payload.verification = { version: 'claim_verifier_v1', state: 'complete', model: 'test-verifier', created_at: new Date().toISOString(), total_claims: 5, eligible_claims: 3,
      model_assessed: 3, gate_assessed: 1, blocked_claims: 1, withheld_model_support: 1, retry_after: null, notes: [], warning: 'Separate model assessment, not legal validation or lawyer approval.' };
    for (const claim of result.payload.claims) {
      if (claim.id === 'C1' || claim.id === 'C4') {
        claim.semantic_status = claim.id === 'C1' ? 'supported' : 'contradicted';
        claim.verification = { origin: 'model', reason: claim.id === 'C1' ? 'The quoted contract expressly states fourteen days after receipt.' : 'The contract states fourteen days, not seven days.', evidence: claim.spans };
      } else if (claim.id === 'C3') {
        claim.semantic_status = 'insufficient_evidence';
        claim.verification = { origin: 'evidence_gate', reason: 'An unresolved question does not establish a conclusion.', evidence: [] };
      } else if (claim.id === 'C5') {
        claim.verification = { origin: 'policy_gate', reason: 'Positive cross-source support requires lawyer review.', evidence: claim.spans,
          model_verdict: 'supported', model_reason: 'The unaccepted model proposal inferred consistency from shared terminology.' };
      }
    }
    await route.fulfill({ json: result });
  });
  await page.route('**/api/reports/verified-synthetic-report/verify', async route => {
    const result = JSON.parse(JSON.stringify(draftReport)); result.id = 'rate-limited-synthetic-report';
    result.payload.verification = { version: 'claim_verifier_v1', state: 'unavailable', model: 'test-verifier', created_at: new Date().toISOString(), total_claims: 4, eligible_claims: 2,
      model_assessed: 0, gate_assessed: 0, blocked_claims: 1, retry_after: 30, notes: ['Verifier rate limit reached. Remaining claims are unchecked.'], warning: 'Separate model assessment, not legal validation.' };
    await route.fulfill({ json: result });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByText('Advanced evidence review', { exact: true }).click();
  await expect(page.getByRole('button', { name: 'Termination & Cure', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByLabel('Matter', { exact: true }).selectOption(matter.id);
  await page.locator('.manual-evidence > summary').click();
  await page.getByLabel('Focused case facts').fill('Synthetic facts: the receipt and remedial access are disputed.');
  await page.getByRole('button', { name: 'Find review passages' }).click();
  await page.getByLabel('Contract clause passage').selectOption(String(contract.chunk_id));
  await page.getByLabel('Authority reasoning passage').selectOption(String(authority.chunk_id));
  const confirmations = page.getByRole('checkbox');
  await confirmations.nth(0).check(); await confirmations.nth(1).check();
  await expect(page.getByRole('button', { name: 'Compare termination issue' })).toBeEnabled();
  await page.getByLabel('Reviewed contract quotation').fill(clause + ' ');
  await expect(confirmations.nth(0)).not.toBeChecked();
  await expect(confirmations.nth(1)).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Compare termination issue' })).toBeDisabled();
  await page.getByLabel('Reviewed contract quotation').fill(clause);
  await confirmations.nth(0).check(); await confirmations.nth(1).check();
  await page.getByRole('button', { name: 'Compare termination issue' }).click();
  const statement = id => page.locator(`[data-report-claim-id=${id}]`);
  await expect(page.getByRole('heading', { name: 'Case Summary', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Possible Arguments and Next Steps', exact: true })).toBeVisible();
  await expect(page.getByText('No claim-level arguments or next steps are available in this draft.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Claims for Review' })).not.toBeVisible();
  await expect(statement('C1')).toContainText('Not assessed - lawyer review required');
  await expect(statement('C2')).toContainText('Evidence check failed - lawyer review required');
  await expect(statement('C3')).toContainText('Insufficient evidence');
  await page.locator('.readable-report').screenshot({ path: testInfo.outputPath('readable-report-desktop.png') });
  await statement('C1').getByRole('button', { name: 'Review evidence for this statement', exact: true }).click();
  await expect(page.locator('[data-claim-id=C1]')).toBeFocused();
  await expect(page.getByRole('heading', { name: 'Reviewed Evidence' })).toBeVisible();
  await expect(page.locator('.reviewed-evidence')).toContainText(clause);
  await expect(page.locator('.reviewed-evidence')).toContainText(reasoning);
  await expect(page.getByRole('heading', { name: 'Claims for Review' })).toBeVisible();
  await expect(page.locator('[data-claim-id=C1] mark')).toHaveText('fourteen days after receipt');
  await expect(page.locator('[data-claim-id=C1]')).toContainText('Not assessed');
  await expect(page.locator('[data-claim-id=C2]')).toContainText('Flagged evidence');
  await expect(page.locator('[data-claim-id=C2]')).toContainText('SYNTHETIC FLAGGED CLAIM: The contract is therefore enforceable.');
  await expect(page.locator('[data-claim-id=C3]')).toContainText('No establishing evidence');
  await page.getByRole('button', { name: 'Verify claims', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Verifier temporarily unavailable.' })).toBeVisible();
  await expect(page.locator('[data-claim-id=C1] [data-assessment]')).toHaveAttribute('data-assessment', 'not_checked');
  await page.getByRole('button', { name: 'Verify claims', exact: true }).click();
  await expect(statement('C1')).toContainText('AI assessment: supported - not lawyer-approved');
  await expect(statement('C4')).toContainText('AI assessment: contradicted by reviewed evidence');
  await expect(statement('C5')).toContainText('Lawyer review required - support not accepted');
  await expect(statement('C5')).not.toContainText('AI assessment: supported');
  await statement('C5').getByRole('button', { name: 'Review evidence for this statement', exact: true }).click();
  await expect(page.locator('[data-claim-id=C1]')).toContainText('AI: supported');
  await expect(page.locator('[data-claim-id=C4]')).toContainText('AI: contradicted');
  await expect(page.locator('[data-claim-id=C3]')).toContainText('Evidence gate: unresolved');
  await expect(page.getByRole('region', { name: 'AI claim verification' })).toContainText('3 of 3 eligible claims assessed');
  await expect(page.locator('[data-claim-id=C5]')).toContainText('Lawyer review required');
  await expect(page.locator('[data-claim-id=C5]')).not.toContainText('AI: supported');
  await expect(page.getByRole('region', { name: 'AI claim verification' })).toContainText('1 cross-source support proposal(s) withheld');
  await page.locator('[data-claim-id=C1]').getByText('Verifier evidence', { exact: true }).click();
  await expect(page.locator('[data-claim-id=C1] .claim-assessment mark')).toHaveText('fourteen days after receipt');
  expect(generationCalls).toBe(1);
  await page.locator('.claim-list').screenshot({ path: testInfo.outputPath('atomic-claims.png') });
  await page.screenshot({ path: testInfo.outputPath('focused-desktop.png'), fullPage: true });
  await page.getByRole('button', { name: 'Verify claims', exact: true }).click();
  await expect(statement('C1')).toContainText('Not assessed - lawyer review required');
  await page.getByText('Review supporting evidence', { exact: true }).click();
  await expect(page.getByRole('button', { name: 'Verify claims', exact: true })).toBeDisabled();
  await expect(page.getByText(/Retry verification in \d+s/)).toBeVisible();
  await expect(page.locator('[data-claim-id=C1] [data-assessment]')).toHaveAttribute('data-assessment', 'not_checked');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('focused-mobile.png'), fullPage: true });
  await page.locator('.reviewed-evidence').getByRole('button', { name: /Synthetic reviewed agreement/ }).click();
  await expect(page.getByRole('dialog')).toContainText(clause);
});

test('readable saved report preserves claims and warnings without generating narrative', async ({ page }, testInfo) => {
  const evidence = { role: 'authority', text: 'Synthetic exact evidence.', start: 0, end: 25, source_id: 55 };
  const scopes = ['case_fact', 'contract_term', 'general_principle', 'authority_case_only', 'comparison', 'not_established'];
  const claims = scopes.map((scope, index) => ({ id: `C${index + 1}`, scope, text: `Original ${scope} statement. Original second sentence.`,
    evidence_check: 'matched', check_issues: [], semantic_status: 'supported', spans: [evidence] }));
  const original = JSON.stringify(claims);
  const report = { id: 'readable-history', kind: 'case_analysis', matter_id: null, query: 'Termination', created_at: new Date().toISOString(),
    payload: { title: 'Saved atomic report', workflow: 'termination_atomic_v2', claims,
      findings: [{ text: 'UNSAFE LEGACY PARAGRAPH MUST NOT APPEAR', source_ids: [] }], limitations: ['Synthetic test only.'],
      sources: [{ chunk_id: 55, document_id: 'test-id', title: 'Synthetic authority', kind: 'judgment', filename: 'test.txt', locator: 'Page 1', text: evidence.text, citation: 'TEST ONLY', court: '', decision_date: '', source_url: '' }] } };
  const aiCalls = [];
  await page.route('**/api/reports', route => route.fulfill({ json: [report] }));
  await page.route('**/api/case-analysis/**', route => { aiCalls.push(route.request().url()); return route.abort(); });
  await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: /Saved atomic report/ }).click();
  await expect(page.locator('.supporting-evidence')).not.toHaveAttribute('open');
  await expect(page.getByText('UNSAFE LEGACY PARAGRAPH MUST NOT APPEAR')).toHaveCount(0);
  for (const claim of claims) await expect(page.locator(`[data-report-claim-id=${claim.id}] .statement-text`)).toHaveText(claim.text);
  await expect(page.getByRole('region', { name: 'Case Summary', exact: true }).locator('[data-report-claim-id]')).toHaveCount(2);
  await expect(page.getByRole('region', { name: 'Relevant Judgments', exact: true }).locator('[data-report-claim-id]')).toHaveCount(2);
  await expect(page.locator('[data-report-claim-id=C5]')).toContainText('Lawyer review required - support not accepted');
  await expect(page.locator('[data-report-claim-id=C6]')).toContainText('Insufficient evidence');
  await page.locator('[data-report-claim-id=C5]').getByRole('button', { name: 'TEST ONLY / Page 1' }).click();
  await expect(page.getByRole('dialog')).toContainText(evidence.text);
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('.readable-report').screenshot({ path: testInfo.outputPath('readable-report-mobile.png') });
  await page.locator('[data-report-claim-id=C5]').getByRole('button', { name: 'Review evidence for this statement', exact: true }).click();
  await expect(page.locator('[data-claim-id=C5]')).toBeFocused();
  expect(aiCalls).toEqual([]);
  expect(JSON.stringify(claims)).toBe(original);
});

test('automatic evidence: one facts confirmation, exact preview, invalidation, role failure and mobile layout', async ({ page, request }, testInfo) => {
  const matter = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name: 'Automatic synthetic matter' } })).json();
  const other = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name: 'Other automatic matter' } })).json();
  const makeSource = (id, kind, text) => ({ chunk_id: id, document_id: `synthetic-${id}`, kind, text, title: kind === 'matter' ? 'Synthetic agreement' : 'Synthetic court reasoning',
    citation: kind === 'matter' ? '' : 'TEST ONLY', locator: 'Page 1', filename: 'synthetic.txt', court: '', decision_date: '', source_url: '' });
  const contract = makeSource(71, 'matter', 'Synthetic clause: written notice and fourteen days after receipt are required before termination.');
  const authority = makeSource(72, 'judgment', 'Synthetic reasoning: a termination clause states the conditions for ending the agreement.');
  const warning = 'Passages selected and roles assessed by AI, not confirmed by a lawyer.';
  let prepareCalls = 0;
  let generationCalls = 0;
  await page.route('**/api/health', route => route.fulfill({ json: { ai_configured: true, model: 'test-model' } }));
  await page.route('**/api/case-analysis/termination/prepare', async route => {
    prepareCalls += 1;
    if (prepareCalls === 1) {
      await route.fulfill({ status: 422, json: { detail: 'The separate evidence-role check could not distinguish reasoning from allegations. Use manual evidence review.' } });
      return;
    }
    expect(route.request().postDataJSON().matter_id).toBe(matter.id);
    await route.fulfill({ json: { selection_id: `preview-${prepareCalls}`, created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + (prepareCalls === 2 ? -1000 : 1800000)).toISOString(),
      contract: { source: contract, quote: contract.text, role: 'contract_term' }, authority: { source: authority, quote: authority.text, role: 'court_reasoning' }, warning,
      coverage: { contract: { candidates: 5, assessed: 3, reduced: true }, authority: { candidates: 8, assessed: 4, reduced: true }, note: 'Keyword-selected candidates only; not a full legal review.' } } });
  });
  await page.route('**/api/case-analysis/termination/automatic', async route => {
    generationCalls += 1;
    const body = route.request().postDataJSON();
    expect(body).toEqual({ matter_id: matter.id, facts: 'Corrected synthetic facts: receipt remains disputed.', selection_id: 'preview-4', confirmed: true });
    await route.fulfill({ json: { id: 'automatic-synthetic-report', kind: 'case_analysis', matter_id: matter.id, query: 'Termination', created_at: new Date().toISOString(),
      payload: { title: 'Termination and cure - atomic evidence review', workflow: 'termination_atomic_v2',
        evidence_selection: { mode: 'ai_selected', warning, model: 'test-model', human_confirmed: ['facts'] },
        evidence_texts: { facts: body.facts, contract: contract.text, authority: authority.text },
        reviewed_evidence: { contract: { source_id: 71, quote: contract.text }, authority: { source_id: 72, quote: authority.text } },
        confirmed_facts: body.facts, findings: [], claims: [{ id: 'C1', scope: 'comparison', text: 'Synthetic cross-source inference remains unresolved.',
          evidence_check: 'matched', check_issues: [], semantic_status: 'not_checked', spans: [], verification: { origin: 'policy_gate', reason: 'Cross-source support withheld.', evidence: [] } }],
        sources: [contract, authority], limitations: ['Synthetic test only.'] } } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByText('Advanced evidence review', { exact: true }).click();
  await page.getByLabel('Matter', { exact: true }).selectOption(matter.id);
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await expect(page.getByLabel('Contract clause passage')).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Case facts', exact: true }).fill('Synthetic facts: receipt remains disputed.');
  await page.getByRole('button', { name: 'Find relevant evidence', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'could not distinguish reasoning' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate case report', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Find relevant evidence', exact: true }).click();
  await expect(page.getByText('This evidence preview has expired. Find relevant evidence again.')).toBeVisible();
  await expect(page.getByRole('checkbox')).toBeDisabled();
  await page.getByRole('button', { name: 'Find relevant evidence', exact: true }).click();
  await expect(page.getByRole('checkbox')).toHaveCount(1);
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toContainText(warning);
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toContainText('3 of 5 contract candidates');
  await page.getByRole('checkbox').check();
  await expect(page.getByRole('button', { name: 'Generate case report', exact: true })).toBeEnabled();
  await page.getByRole('textbox', { name: 'Case facts', exact: true }).fill('Corrected synthetic facts: receipt remains disputed.');
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Generate case report', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Find relevant evidence', exact: true }).click();
  await expect(page.getByRole('checkbox')).not.toBeChecked();
  await page.getByRole('button', { name: 'TEST ONLY / Page 1', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText(authority.text);
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('automatic-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('automatic-mobile.png'), fullPage: true });
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Generate case report', exact: true }).click();
  await expect(page.locator('.report').getByRole('alert').filter({ hasText: warning })).toBeVisible();
  await expect(page.locator('[data-report-claim-id=C1]')).toContainText('Lawyer review required');
  expect(generationCalls).toBe(1);
  await page.getByRole('textbox', { name: 'Case facts', exact: true }).fill('Further corrected synthetic facts.');
  await expect(page.locator('.report')).toHaveCount(0);
  await page.getByLabel('Matter', { exact: true }).selectOption(other.id);
  await expect(page.getByRole('textbox', { name: 'Case facts', exact: true })).toHaveValue('');
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toHaveCount(0);
});

test('Groq cooldown disables AI actions, keeps facts and preview, and waits for a manual retry', async ({ page, request }, testInfo) => {
  const matter = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name: 'Synthetic cooldown matter' } })).json();
  await page.clock.install();
  await page.route('**/api/health', route => route.fulfill({ json: { ai_configured: true, model: 'test-model' } }));
  const source = { chunk_id: 71, document_id: 'synthetic-cooldown', kind: 'matter', text: 'Synthetic termination clause: allow fourteen days after receipt.',
    title: 'Synthetic agreement', citation: '', locator: 'Page 1', filename: 'test.txt', court: '', decision_date: '', source_url: '' };
  const headers = { 'Retry-After': '14', 'Access-Control-Expose-Headers': 'Retry-After', 'Access-Control-Allow-Origin': 'http://127.0.0.1:5176' };
  let prepares = 0;
  let generations = 0;
  await page.route('**/api/case-analysis/termination/prepare', async route => {
    prepares += 1;
    if (prepares === 1) { await route.fulfill({ status: 429, headers, json: { detail: 'Temporary rate limit. Completed stages saved.' } }); return; }
    await route.fulfill({ json: { selection_id: 'saved-preview', created_at: new Date().toISOString(), expires_at: new Date(Date.now() + 1800000).toISOString(),
      contract: { source, quote: source.text, role: 'contract_term' }, authority: { source: { ...source, kind: 'judgment' }, quote: source.text, role: 'court_reasoning' },
      warning: 'Synthetic AI-selected evidence only.', coverage: { note: 'Limited coverage.', contract: { candidates: 1, assessed: 1 }, authority: { candidates: 1, assessed: 1 } } } });
  });
  await page.route('**/api/case-analysis/termination/automatic', async route => {
    generations += 1;
    if (generations === 1) { await route.fulfill({ status: 429, headers, json: { detail: 'Temporary rate limit.' } }); return; }
    await route.fulfill({ status: 503, json: { detail: 'Synthetic stop after checking manual retry.' } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByText('Advanced evidence review', { exact: true }).click();
  await page.getByLabel('Matter', { exact: true }).selectOption(matter.id);
  const facts = page.getByRole('textbox', { name: 'Case facts', exact: true });
  const find = page.getByRole('button', { name: 'Find relevant evidence', exact: true });
  const generate = page.getByRole('button', { name: 'Generate case report', exact: true });
  await facts.fill('Synthetic facts must remain unchanged during cooldown.');
  await find.click();
  await expect(page.getByRole('status')).toContainText(/Retry AI requests in 1[34]s/);
  await expect(find).toBeDisabled();
  await expect(facts).toHaveValue('Synthetic facts must remain unchanged during cooldown.');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('cooldown-mobile.png'), fullPage: true });
  await page.clock.fastForward(15000);
  await expect(find).toBeEnabled();
  expect(prepares).toBe(1);
  await find.click();
  await page.getByRole('checkbox').check();
  await generate.click();
  await expect(generate).toBeDisabled();
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toBeVisible();
  await expect(page.getByRole('checkbox')).toBeChecked();
  await page.clock.fastForward(15000);
  await expect(generate).toBeEnabled();
  expect(generations).toBe(1);
  await generate.click();
  await expect(page.getByRole('alert')).toContainText('Synthetic stop after checking manual retry.');
  expect(prepares).toBe(2);
  expect(generations).toBe(2);
});

test('blocked role check shows candidates and reasons, and manual recovery retains the flags', async ({ page, request }, testInfo) => {
  const matter = await (await request.post('http://127.0.0.1:8012/api/matters', { data: { name: 'Synthetic role-flag review' } })).json();
  await page.route('**/api/health', route => route.fulfill({ json: { ai_configured: true, model: 'test-model' } }));
  const source = (id, kind, text) => ({ chunk_id: id, document_id: `flagged-${id}`, kind, text,
    title: kind === 'matter' ? 'Synthetic agreement' : 'Synthetic authority', citation: kind === 'matter' ? '' : 'TEST ONLY',
    locator: 'Page 1', filename: 'test.txt', court: '', decision_date: '', source_url: '' });
  const contract = source(91, 'matter', 'Synthetic agreement term: written notice must allow fourteen days after receipt.');
  const authority = source(92, 'judgment', 'Synthetic authority: a termination clause sets the conditions for ending an agreement.');
  const issues = [{ role: 'authority', code: 'authority_role_disagreement', message: 'The AI role check classified the authority quotation as uncertain; it disagreed with the selector.' }];
  let prepares = 0;
  let comparisons = 0;
  let candidateCalls = 0;
  await page.route('**/api/case-analysis/termination/prepare', async route => {
    prepares += 1;
    await route.fulfill({ status: 422, json: { detail: { code: 'evidence_role_review_required',
      message: 'Automatic evidence selection needs human review. No report was generated.',
      review: { review_id: 'flagged-review', issues, contract: { source: contract, quote: contract.text, role: 'contract_term' },
        authority: { source: authority, quote: authority.text, role: 'court_reasoning' } } } } });
  });
  await page.route('**/api/case-analysis/termination/evidence', route => { candidateCalls += 1; return route.abort(); });
  await page.route('**/api/case-analysis/termination', async route => {
    comparisons += 1;
    const body = route.request().postDataJSON();
    expect(body.role_review_id).toBe('flagged-review');
    expect(body.contract).toEqual({ source_id: 91, quote: contract.text });
    expect(body.authority).toEqual({ source_id: 92, quote: authority.text });
    expect(body.confirmed).toBe(true);
    expect(body.reasoning_confirmed).toBe(true);
    await route.fulfill({ json: { id: 'manually-reviewed-test', kind: 'case_analysis', matter_id: matter.id, query: 'Termination', created_at: new Date().toISOString(),
      payload: { title: 'Termination and cure - atomic evidence review', workflow: 'termination_atomic_v2', findings: [],
        evidence_selection: { mode: 'manual_after_role_flag', model: 'test-model', warning: 'Automatic evidence-role selection was blocked. Original role flags are retained.', original_issues: issues },
        sources: [contract, authority], limitations: ['Synthetic test only.'], claims: [{ id: 'C1', scope: 'not_established', text: 'Synthetic unresolved issue remains open.',
          evidence_check: 'no_evidence', semantic_status: 'insufficient_evidence', check_issues: [], spans: [] }] } } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Case Analysis', exact: true }).click();
  await page.getByText('Advanced evidence review', { exact: true }).click();
  await page.getByLabel('Matter', { exact: true }).selectOption(matter.id);
  await page.getByRole('textbox', { name: 'Case facts', exact: true }).fill('Synthetic facts for an evidence-role review.');
  await page.getByRole('button', { name: 'Find relevant evidence', exact: true }).click();
  const blocked = page.getByRole('region', { name: 'Evidence requiring review' });
  await expect(blocked).toContainText(issues[0].message);
  await expect(blocked).toContainText(contract.text);
  await expect(blocked).toContainText(authority.text);
  await expect(page.getByRole('button', { name: 'Generate case report', exact: true })).toBeDisabled();
  await blocked.getByRole('button', { name: 'TEST ONLY / Page 1', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText(authority.text);
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('blocked-review-mobile.png'), fullPage: true });
  await page.getByRole('button', { name: 'Review selected passages', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Reviewed contract quotation', exact: true })).toHaveValue(contract.text);
  await expect(page.getByRole('textbox', { name: 'Reviewed authority quotation', exact: true })).toHaveValue(authority.text);
  const confirmations = page.getByRole('checkbox');
  await expect(confirmations).toHaveCount(2);
  await expect(confirmations.nth(0)).not.toBeChecked();
  await expect(confirmations.nth(1)).not.toBeChecked();
  const compare = page.getByRole('button', { name: 'Compare termination issue', exact: true });
  await expect(compare).toBeDisabled();
  await confirmations.nth(0).check();
  await expect(compare).toBeDisabled();
  expect(comparisons).toBe(0);
  await confirmations.nth(1).check();
  await compare.click();
  await expect(page.locator('.report').getByRole('heading', { name: 'Earlier automatic selection flags', exact: true })).toBeVisible();
  await expect(page.locator('.report')).toContainText(issues[0].message);
  await expect(page.locator('[data-report-claim-id=C1]')).toContainText('Insufficient evidence');
  expect(prepares).toBe(1);
  expect(comparisons).toBe(1);
  expect(candidateCalls).toBe(0);
});

test('focused application report preserves source qualifications and shows comparisons or gaps per topic', async ({ page }, testInfo) => {
  const contract = 'Written notice must allow fourteen days after receipt. The customer shall provide reasonable remedial access.';
  const facts = 'Notice was sent on 10 August and termination followed on 27 August, with receipt disputed.';
  const authority = 'Without such a clause, unilateral termination would typically constitute a breach.';
  const texts = { contract, facts, authority };
  const source = (id, kind, text) => ({ chunk_id: id, document_id: `application-${id}`, kind, text,
    title: kind === 'matter' ? 'Synthetic agreement' : 'Synthetic judgment', citation: kind === 'matter' ? '' : 'TEST ONLY',
    locator: 'Page 1', filename: 'test.txt', court: '', decision_date: '', source_url: '' });
  const span = role => ({ role, source_id: role === 'facts' ? null : role === 'contract' ? 31 : 32, text: texts[role], start: 0, end: texts[role].length });
  const observation = (id, scope, role) => ({ id, scope, text: texts[role], wording_origin: 'source_text', spans: [span(role)],
    evidence_check: 'matched', semantic_status: 'not_checked', check_issues: [] });
  const claims = [observation('C1', 'contract_term', 'contract'), observation('C2', 'case_fact', 'facts'), observation('C3', 'general_principle', 'authority'),
    { id: 'C4', scope: 'not_established', application_topic: 'notice_and_cure', application_alignment: 'aligned_sources', wording_origin: 'review_question', text: 'Does the reviewed chronology establish the opportunity to remedy required by the quoted contract condition?',
      spans: [span('contract'), span('facts'), span('authority')], evidence_check: 'matched', semantic_status: 'insufficient_evidence', check_issues: [] },
    ...[['C5', 'remedial_access', 'What reviewed evidence resolves the parties\' dispute about reasonable remedial access?'],
        ['C6', 'material_breach', 'What reviewed evidence establishes materiality without adding a test absent from these excerpts?']].map(([id, application_topic, text]) => ({
          id, scope: 'not_established', application_topic, application_alignment: 'evidence_gap', wording_origin: 'review_question', text, spans: [], evidence_check: 'no_evidence',
          semantic_status: 'insufficient_evidence', check_issues: [] }))];
  await page.route('**/api/reports', route => route.fulfill({ json: [{ id: 'application-report', kind: 'case_analysis', matter_id: null,
    query: 'Termination', created_at: new Date().toISOString(), payload: { title: 'Focused application test', workflow: 'termination_atomic_v2', claim_format: 'focused_references_v2',
      claims, evidence_texts: texts, sources: [source(31, 'matter', contract), source(32, 'judgment', authority)], findings: [], limitations: ['Synthetic test only.'],
      verification: { version: 'claim_verifier_v1', state: 'unavailable', model: 'test-model', created_at: new Date().toISOString(), total_claims: 6, eligible_claims: 3,
        model_assessed: 0, gate_assessed: 3, blocked_claims: 0, withheld_model_support: 0, retry_after: null, notes: [], warning: 'Synthetic assessment only.' } } }] }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByRole('button', { name: /Focused application test/ }).click();
  await expect(page.locator('.readable-report').getByRole('status')).toContainText('AI verification incomplete: 0 of 3');
  await expect(page.locator('[data-report-claim-id=C3] .statement-text')).toHaveText(authority);
  await expect(page.locator('[data-report-claim-id=C2] .statement-text')).toHaveText(facts);
  const application = page.getByRole('region', { name: 'How They Relate to Your Case', exact: true });
  await expect(application.getByRole('heading', { name: 'Notice and cure', exact: true })).toBeVisible();
  await expect(application.getByRole('heading', { name: 'Remedial access', exact: true })).toBeVisible();
  await expect(application.getByRole('heading', { name: 'Material breach', exact: true })).toBeVisible();
  await expect(application.locator('[data-report-claim-id]')).toHaveCount(3);
  await expect(application.locator('[data-report-claim-id=C4]')).toContainText('Review question - no legal conclusion');
  await expect(application.locator('[data-report-claim-id=C4] .application-evidence')).toContainText(facts);
  await expect(application.locator('[data-report-claim-id=C4] .application-evidence')).toContainText(authority);
  await expect(application.locator('[data-report-claim-id=C5]')).toContainText('Evidence gap - review required');
  await expect(application.locator('[data-report-claim-id=C6]')).toContainText('Evidence gap - review required');
  await page.locator('.readable-report').screenshot({ path: testInfo.outputPath('application-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('.readable-report').screenshot({ path: testInfo.outputPath('application-mobile.png') });
  await application.locator('[data-report-claim-id=C5]').getByRole('button', { name: 'Review evidence for this statement' }).click();
  await expect(page.locator('[data-claim-id=C5]')).toBeFocused();
});
