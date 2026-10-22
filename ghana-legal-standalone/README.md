# Ghana Legal Workspace

A standalone Ghana-focused legal research and case-analysis prototype within the
AI Compliance Platform repository. It follows the React/FastAPI approach used by
AfriSafeBench while keeping its own API, dependencies, configuration and data.

## First Working Version

- Dashboard with real matter, document, authority and saved-report counts.
- Matter creation and separate matter-document collections.
- Shared judgment/statute library with court, citation, date and provenance metadata.
- PDF, DOCX and UTF-8 TXT uploads, original-file downloads and persistent indexing.
- Keyword-ranked source search, with PDF page or DOCX/TXT paragraph/table locators.
- Optional Groq-backed question answering with clickable source passages.
- One-action focused termination analysis: select a matter, upload case documents,
  click `Analyze Case`, and read a sourced draft with comparisons, conditional
  arguments and explicit gaps. Progress and completed stages survive interruption.
  See [One-Action Case Analysis](docs/case_workflow.md).
  The older quotation-selection route remains under `Advanced evidence review`.
  Broad general analysis remains paused pending the checked multi-issue workflow.
- Source-linked factual excerpts preserve party attribution and documentary caveats;
  new focused reports use uploaded documents rather than verifying an entered summary
  against itself. See [Source-Linked Case Facts](docs/document_facts.md).
- Saved reports with their retrieved passages and JSON export.

There are no bundled judgments, fabricated case authorities or external database
connections. Upload documents you are authorised to process. A judgment/statute is
shared across matters in this workspace; a matter file is only included in research
when that matter is explicitly selected. Source metadata is user-supplied, not verified.

## Structure

```text
ghana-legal-standalone/
  backend/legal_app/    Independent FastAPI package (no parent imports)
  frontend/            React + TypeScript + Vite interface
  data/                Local SQLite FTS5 database and original uploads (gitignored)
  tests/               API, isolation, persistence and extraction tests
  .env.example         Optional AI connection and API settings
  requirements.txt     Backend runtime dependencies
```

## Run Locally

From `ghana-legal-standalone/`, create a dedicated virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Optionally create `.env` from `.env.example` and set `GROQ_API_KEY`. The legal app
does not automatically read the parent project's `.env`. Process environment variables
override this app's `.env`. Never place a provider key in frontend configuration.
Without a key, uploads, matters, the dashboard and passage search work; AI features
are unavailable.

AI requests default to a 4,000-token input budget (including prompt/schema and a
chat-framing reserve) and a 3,000-token maximum completion. Whole passages are selected
across source documents, preserving their original text and citation IDs. Reports
disclose when retrieved passages were omitted; case briefs flag incomplete coverage.
Confirmed facts and questions are never silently shortened. Optional `.env` settings
are `LEGAL_MAX_INPUT_TOKENS` and `LEGAL_MAX_COMPLETION_TOKENS`; keep their sum below
your account's per-request/token allowance. Temporary token-rate limits may still
require waiting between calls and are reported separately from authentication errors.
Recognised provider structured-generation failures (HTTP 400) are retried once with
the same strict schema and local validation. Unknown bad requests and rate limits
are not automatically retried; rate-limit responses include a retry delay. A successful
retry is not a guarantee of legal correctness or ongoing provider availability.
The GPT-OSS tokenizer is used for GPT-OSS models; other models use a conservative
encoding estimate and should be verified against their provider allowance. On first
use, tiktoken downloads and caches its public encoding data; subsequent uses reuse it.

New focused comparisons retain the entered summary separately and build their factual
evidence from source-linked private case excerpts. Earlier paragraph comparisons passed
the confirmed summary, selected private passages and authorities separately. Judgments
are not expected to contain the current case's facts. Case-file citations support
factual evidence; comparisons and possible legal approaches must cite at least one
retrieved authority. Evidence gaps are labelled separately, and a gap-only answer is
not saved as a successful case comparison. Saved source passages identify their role.
Legal findings also require short supporting quotations, checked against the cited
passage after whitespace normalisation. Exact quote matching does not establish that
the legal inference is correct. Reports created before these checks show a regeneration
warning. Search ignores common question words and legacy inline source-ID markers,
while preserving legal negation terms such as `not`.

GPT-OSS requests use [Groq strict structured outputs](https://console.groq.com/docs/structured-outputs)
to enforce the report shape. The schema is included once in the token budget; other
models retain JSON-object mode and local validation. Schema/quotation checks are not
semantic legal validation. Live sample tests still produced unsupported contract
interpretations despite matching quotations. Treat all case reports as unverified
drafts, not legal advice or a validated case recommendation.

Start the backend from `ghana-legal-standalone/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn legal_app.main:app --app-dir backend --host 127.0.0.1 --port 8011
```

Or, during development, use the parent repository's existing Python environment:

```powershell
..\venv\Scripts\python.exe -m uvicorn legal_app.main:app --app-dir backend --host 127.0.0.1 --port 8011
```

In another terminal, from `ghana-legal-standalone/frontend/`:

```powershell
npm install
npm run dev
```

- Workspace: http://127.0.0.1:5175
- API documentation: http://127.0.0.1:8011/docs

The ports are distinct from the parent app and AfriSafeBench. If changing the frontend
origin, update `LEGAL_CORS_ORIGINS`. For another backend URL, set
`VITE_API_BASE_URL` using `frontend/.env.example` and restart Vite.

## First Use

1. Create a matter, then upload case documents as **Private matter file**.
2. Upload permitted judgments/statutes to the **Legal library**, including provenance.
3. Open **Legal Research** to search passages or generate a cited answer.
4. Open **Case Analysis**, select a matter, and extract a proposed brief or enter facts.
   Correct the facts and choose **Find relevant evidence** for the termination issue.
5. Inspect the selected evidence, confirm the facts, and **Generate case report**.
   Open cited passages and download original documents; these remain AI-generated drafts.
6. Reopen saved work in **Reports**. Documents and reports survive server restarts.

### Focused Termination Review

Case Analysis opens on **Termination & Cure**. Select a matter, review the facts and
choose **Find relevant evidence**. The app selects exact quotations and runs a separate
AI passage-role check. Inspect the preview, confirm the facts with one checkbox, then
choose **Generate case report**. Role uncertainty stops selection rather than silently
using allegations as reasoning. Model role assessments remain fallible, not lawyer review.
The preview discloses candidate coverage and expires after 30 minutes; changing facts
or relevant documents requires a fresh selection. See [automatic evidence selection](docs/automatic_evidence.md).

**Manual evidence review** retains the original passage dropdowns, editable quotations
and two explicit human confirmations. Keyword candidate search in that path needs no
AI connection. Automatic selection uses up to three logical provider calls before the
existing generation/verifier calls, so token/request limits may require waiting.
If selection is rate-limited, completed selection stages are retained for a manual retry;
the app shows a cooldown and resumes unfinished stages without repeating completed ones.
Facts, sources, context or configuration changes invalidate stale progress. Do not repeat
a successful brief extraction merely because a later selection request was rate-limited.
If the role check blocks selection, the app shows its specific reason and the exact
candidate quotations. **Review selected passages** opens manual review with neither
confirmation pre-ticked. Original AI flags remain visible in any resulting manual report;
this does not automatically approve the passages or establish lawyer validation.

Only the reviewed quotations and factual premise are sent for this focused comparison.
New drafts use [source-text observations and required case-review topics](docs/focused_case_application.md).
Observations retain exact source wording and qualifications. Notice/cure, remedial access
and material breach each show a source-alignment record and specific review question,
not a generated compliance verdict. Missing evidence and incomplete AI verification remain
visible; a source-alignment record is not a legal conclusion or an entitlement to a remedy.
Surrounding passages are available for human review, but are not silently inserted or
truncated into the model input. New reports contain short claims with scope labels and
highlighted spans from the contract, reviewed authority or confirmed factual premise.
Missing or invented spans and role mismatches are flagged and retained for inspection.
**Spans matched** means only that the text occurs in the reviewed evidence. A separate
batched verifier now assesses eligible claims as supported, contradicted or insufficient
evidence. Its results are explicitly labelled **AI** assessments, not legal validation.
Unavailable, invalid or over-budget checks leave claims unassessed rather than approved.
Positive cross-source support proposals are withheld for lawyer review even when the
model says supported; an actual saved-draft regression exposed that failure mode.

Neither automatic nor manual selection establishes reliable clause extraction or legal
validation. Live tests still overgeneralised some quoted propositions;
do not treat its output as a validated recommendation. See
[the sample review checklist](docs/termination_review.md) and
[claim evaluation protocol](docs/atomic_claim_evaluations.md). **General Analysis** is
paused for new reports (API returns HTTP 409). Existing paragraph-format reports remain
readable, with a legacy warning. Research, search and document management are unchanged.

There are 12 synthetic evaluation fixtures (8 development, 4 held out), labelled claim
probes, an offline screening runner and an opt-in live baseline/atomic comparison.
These are engineering evidence-comprehension tests, not expert-validated Ghanaian legal
opinions. See [the verifier protocol](docs/claim_verifier.md) for batching, safeguards and
annotated-probe evaluation. Persisted lawyer approval remains future work.

Saved atomic reports have a **Verify claims** action. It checks the original quotations
again, does not regenerate claim text, and saves a new assessment version while retaining
the original report. A rate-limit cooldown prevents immediate repeated retries.

## Relation To The Parent Project

This is a separate product workspace in the same repository, like
`afrisafebench-standalone/`. It reuses the parent's architectural approach and the same
provider/extraction libraries, but not the privacy/FDA/healthcare corpus, storage or
Python imports. It can be copied to its own repository and run independently.
Future shared APIs can be added explicitly; there is currently no network integration
with the parent app and no data synchronisation between them.

## API

```text
GET  /api/health
GET  /api/dashboard
GET  /api/matters
POST /api/matters
GET  /api/documents
POST /api/documents                 Multipart upload and metadata
GET  /api/documents/{id}/download
GET  /api/passages/{chunk_id}
POST /api/search                    query, scope, optional matter_id
POST /api/research                  Same search scope; returns a saved AI report
POST /api/case-analysis/brief        matter_id; returns an editable draft
POST /api/case-analysis/termination/evidence  Keyword matches and neighbouring passages
POST /api/case-analysis/termination  Reviewed quotations, facts and two confirmations
POST /api/reports/{id}/verify        Separate verifier pass; saves a new assessment version
POST /api/case-analysis              matter_id, facts, issues, confirmed=true
GET  /api/reports
```

## Checks

From `ghana-legal-standalone/` with backend dependencies and `httpx` installed:

```powershell
..\venv\Scripts\python.exe -m unittest discover -s tests -v
```

From `frontend/`:

```powershell
npm run build
```

Tests use temporary databases and synthetic test text, with no Groq calls.

Browser checks use a separate API on port 8012, a separate Vite server on 5176,
and an ignored test database. From `frontend/`, with a Python interpreter containing
the backend dependencies:

```powershell
$env:LEGAL_TEST_PYTHON = (Resolve-Path ..\..\venv\Scripts\python.exe).Path
npx playwright install chromium
npm run test:e2e
```

Use a different interpreter path for a dedicated legal virtual environment. Browser
tests exercise real uploads/search/downloads and use explicitly synthetic mocked AI
responses to test the review/citation interface without external model calls.

## Current Boundaries

- Local, single-workspace prototype. No login, firm-level access control, encryption
  at rest or audit trail. Matter scope filters are not an authorisation system.
  Keep the server on localhost; authentication and tenant isolation are required
  before confidential multi-user or public deployment.
- Search uses SQLite FTS5/BM25, not semantic embeddings or a verified citator. It
  does not establish precedent hierarchy, binding effect or subsequent treatment.
- AI reports use retrieved passages only. Citation IDs are validated, but their
  substantive support still requires review. Unsupported citations reject the report.
- Proposed briefs select from at most the first 40 case passages and explicitly flag
  incomplete coverage. Precedent analysis selects from up to 20 retrieved authority
  passages within the request budget, using lawyer-confirmed facts/issues; it is not
  exhaustive review of every document.
- Selected case passages and facts are sent to Groq when an AI action is requested.
  Uploading/indexing and keyword search run locally. Confirm applicable provider and
  client confidentiality requirements before using real client material.
- Upload limits: 20 MB per file, 500 PDF pages, 2 million extracted characters;
  expanded DOCX contents limited to 50 MB. Scanned PDFs need external OCR first.
- No automatic court updates, judgment scraping, deadline computation/reminders,
  contract risk scoring or legal compliance certification.
- Persistent uploads/reports currently have no deletion interface. Retention,
  deletion, backups and lifecycle controls remain production work.

Next modules: licensed Ghanaian authority ingestion, richer/hybrid legal retrieval,
verified authority metadata, authentication, matter permissions, contract/policy review,
and lawyer-confirmed deadlines. Dashboard metrics should follow real module data.
