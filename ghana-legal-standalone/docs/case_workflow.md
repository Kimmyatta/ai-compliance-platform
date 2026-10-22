# One-Action Case Analysis

The default Case Analysis screen now starts a persistent local job with one
`Analyze Case` action. The first supported scope is termination, notice, cure,
remedial access and alleged material breach. It is not general whole-case analysis.
The older passage-selection workflow remains under `Advanced evidence review`.
Existing reports, API routes, uploads and source collections are preserved.

## Processing

1. Select matter-scoped document evidence. Passage selection is distributed across
   documents and page ranges under a disclosed 40-passage cap, not the first file's
   first forty passages. Final excerpts retain their original source order.
2. Build an extractive factual brief. Reserve complete receipt/access chronology
   bundles, then distribute remaining input space across issues, documents and pages.
   Server-retained chronology cannot be erased by the model selecting early facts.
3. Select operative contract terms. Search the uploaded authority library separately
   for each focused issue, including neighbouring passages from the same document.
4. Select an authority quotation and separately check source roles. Allegations,
   submissions and uncertain attribution do not authorize an application. A failed
   issue becomes an explicit gap; other issues continue.
5. Generate source-ID observations and narrow atomic applications: similarity,
   difference, arguments for and against termination, and a weakness. An unavailable
   application uses fixed gap wording instead of invented legal prose.
6. Match references and source roles, then run the existing separate AI assessor.
   Comparisons need contract, case-document and authority evidence. Even proposed
   positive support remains behind the cross-source lawyer-review gate.
7. Assemble the six report headings from those records, without another narrative
   generation call. Unsupported, contradicted, malformed and unchecked applications
   are withheld from the main report. Original text is available only in supporting
   evidence with an explicit unaccepted-draft label.

## API And Persistence

- `POST /api/case-analysis/jobs` with `matter_id` starts or returns matching active work.
- `GET /api/case-analysis/jobs?matter_id=...` lists that matter's recent job statuses.
- `GET /api/case-analysis/jobs/{id}` returns progress and the completed report, if any.
- `POST /api/case-analysis/jobs/{id}/resume` explicitly resumes saved work.

SQLite retains completed stages and assessed claim batches. A provider rate limit
pauses the job with a retry time; the UI does not automatically make another AI
request. Refreshing the page restores pending work. API startup pauses interrupted
queued/running work for explicit resume. Source collection, model, budgets, schemas
and prompt fingerprints invalidate stale work rather than combining old and new
evidence. Report creation and completed-job status commit in one transaction.

This uses FastAPI background tasks and local process locks, not a production task
queue. The prototype remains a single-workspace, single-API-process application
without authentication or tenant isolation. Do not expose it as a law-firm service
without the separate security and deployment work.

## Evidence Boundaries

Keyword retrieval is not exhaustive research or a determination of legal relevance.
Source-exact text does not prove an allegation. A same-model verifier can still make
semantic mistakes. A draft comparison marked for lawyer review is not lawyer-approved
or an accepted legal conclusion. Authority currency, hierarchy, subsequent treatment,
full judgment context, privilege and documentary accuracy require qualified review.
The report does not invent decisions when the selected reasoning lacks a disposition.

No external judgment service is queried. No new provider requests are made by local
unit tests or browser fixtures. A live run sends selected case excerpts to the
configured provider and uses that account's quota; it must be authorized separately.

## Verification

Backend regressions cover later-page receipt/access inclusion, exact provenance,
per-issue role failures, incorrect references, withheld applications, idempotency,
rate-limit checkpoint recovery, process interruption, stale collections, report
immutability and private-matter isolation. Browser tests cover the one-action flow,
six report sections, inline review marks, hidden unsupported text, citation inspection,
desktop/mobile layout and explicit resume after page reload.

These tests establish workflow behavior, not legal accuracy. A complete live EHL/ECS
report still needs a separately authorized provider run and lawyer assessment.
