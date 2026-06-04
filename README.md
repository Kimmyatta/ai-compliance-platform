# AI Compliance Platform

AI Compliance Platform is a regulatory review and audit platform for privacy documents and FDA-cleared AI/ML medical device submissions. Version 1.0 began as a Streamlit-based compliance review assistant for HIPAA, CCPA, and HITECH. The current phase adds an FDA AI device audit workflow and starts the transition toward a production-style architecture using FastAPI and a future React + TypeScript frontend.

The platform supports two core workflows:

- Ask compliance questions and retrieve relevant regulatory context.
- Upload documents and generate structured compliance review feedback.
- Audit FDA-cleared AI/ML device submissions against FDA AI/ML guidance.

## Platform Architecture

The project is moving from a Streamlit-only prototype toward a frontend/backend platform:

```text
React + TypeScript frontend
        |
        v
FastAPI backend
        |
        v
Python review and audit services
        |
        v
FAISS indexes, source PDFs, extracted text, and LLM calls
```

Streamlit is still useful for local prototyping and testing. FastAPI is the backend layer that React will call. The React frontend should not import Python files directly; it should send requests to FastAPI endpoints and render the JSON responses.

## Version 1.0

Version 1.0 provides a working regulatory review pipeline for HIPAA, CCPA, and HITECH.

Key capabilities include:

- Local regulatory knowledge base built from raw PDF files.
- PDF text extraction into plain text.
- Text cleaning and chunking for retrieval.
- Sentence-transformer embeddings using `BAAI/bge-small-en-v1.5`.
- FAISS vector search for retrieving relevant regulatory sections.
- Streamlit interface for compliance Q&A.
- Document upload support for PDF, DOCX, and TXT files.
- Multi-regulation document review across HIPAA, CCPA, and HITECH.
- Risk scoring and structured review output.
- PDF export for compliance reports.
- Local logging of review activity.

The Version 1.0 privacy review knowledge base is organized under `data/privacy/`:

```text
data/privacy/raw/          HIPAA, CCPA, and HITECH source PDFs
data/privacy/extracted/    Extracted text from privacy PDFs
data/privacy/cleaned/      Cleaned privacy text files
data/privacy/chunked/      Chunked privacy text used for retrieval
data/privacy/embeddings/   Generated privacy embedding JSON
data/privacy/faiss_index/  Privacy FAISS index and metadata
```

## Next Phase

The next phase expands the platform into an auditing framework that systematically evaluates FDA-cleared AI medical device submissions against existing FDA guidance documents, identifying compliance gaps between what the FDA recommends and what manufacturers actually disclose.

This direction will focus on FDA-cleared AI/ML-enabled medical devices and their public submission materials. The goal is to compare disclosed device information against FDA expectations for AI/ML-enabled software, including model transparency, intended use, validation evidence, performance reporting, risk management, change control, human factors, monitoring, and cybersecurity considerations.

Planned capabilities include:

- Ingesting FDA-cleared device PDFs and FDA AI/ML guidance documents.
- Classifying device submissions by specialty, intended use, and AI/ML function.
- Extracting manufacturer disclosures from 510(k), De Novo, and related public documents.
- Mapping disclosures against FDA guidance expectations.
- Flagging missing, weak, or ambiguous disclosure areas.
- Producing structured audit summaries for each device.
- Supporting cross-device comparison by clinical area or regulatory topic.
- Maintaining traceable evidence links back to source document sections.

The FDA AI device audit data is separated into guidance documents and device submissions:

```text
data/fda_ai/guidance/raw/          FDA guidance source PDFs
data/fda_ai/guidance/extracted/    Extracted guidance text
data/fda_ai/guidance/cleaned/      Cleaned guidance text
data/fda_ai/guidance/chunked/      Chunked guidance text used for retrieval
data/fda_ai/guidance/embeddings/   Generated guidance embedding JSON
data/fda_ai/guidance/faiss_index/  FDA guidance FAISS index and metadata

data/fda_ai/devices/raw/           FDA-cleared device submission PDFs
data/fda_ai/devices/extracted/     Extracted device submission text
data/fda_ai/devices/cleaned/       Cleaned device submission text
data/fda_ai/devices/parsed/        Structured manufacturer disclosures
data/fda_ai/devices/audited/       Final audit outputs and gap reports
```

## FastAPI Backend

The backend lives under `backend/` and exposes the current Python workflows as API endpoints.

```text
backend/
├── app/
│   ├── main.py
│   ├── api/routes.py
│   ├── services/
│   │   ├── fda_audit_service.py
│   │   ├── privacy_review_service.py
│   │   ├── pdf_service.py
│   │   └── retrieval_service.py
│   ├── models/schemas.py
│   └── core/config.py
├── requirements.txt
└── README.md
```

Initial API endpoints:

```text
GET  /api/health
GET  /api/fda-audit/devices
POST /api/fda-audit/upload
POST /api/fda-audit/devices/{filename}
POST /api/fda-audit/jobs/upload
POST /api/fda-audit/jobs/devices/{filename}
GET  /api/fda-audit/jobs
GET  /api/fda-audit/jobs/{job_id}
POST /api/privacy-review/upload
```

The two FDA audit POST endpoints both generate FDA audit reviews, but they support different workflows:

```text
POST /api/fda-audit/devices/{filename}
```

Audits an existing cleaned device file from `data/fda_ai/devices/cleaned/`.

```text
POST /api/fda-audit/upload
```

Audits a newly uploaded PDF, DOCX, or TXT file.

For React, the preferred FDA audit workflow is the job-based API:

```text
POST /api/fda-audit/jobs/upload
POST /api/fda-audit/jobs/devices/{filename}
GET  /api/fda-audit/jobs/{job_id}
```

The POST endpoint starts an audit and returns immediately:

```json
{
  "job_id": "example-job-id",
  "status": "queued",
  "filename": "uploaded_device.pdf"
}
```

The frontend can then poll the job status endpoint until the job returns `completed` or `failed`.

The current job store is in memory. This is suitable for local development and React integration, but AWS production should replace it with a persistent store such as Redis, DynamoDB, RDS, or S3-backed job records.

Run the backend from the project root:

```powershell
.\venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/docs
```

The `/docs` page is generated automatically by FastAPI and can be used to test each endpoint.

## React + TypeScript Frontend Plan

The planned frontend will use React + TypeScript. React will become the user-facing application, while FastAPI remains responsible for the Python-heavy work: PDF extraction, FAISS retrieval, FDA audit logic, privacy review logic, LLM calls, parsing, and report generation.

Planned frontend structure:

```text
frontend/
├── src/
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   ├── pages/
│   │   ├── PrivacyReview.tsx
│   │   ├── FdaAudit.tsx
│   │   └── AuditHistory.tsx
│   ├── types/
│   │   └── audit.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── vite.config.ts
└── tsconfig.json
```

Expected frontend responsibilities:

- Provide document upload screens for privacy review and FDA audit.
- Display audit progress, errors, and completed results.
- Render FDA audit dimensions, risk levels, evidence sources, and guidance gaps.
- Render privacy review findings across HIPAA, CCPA, and HITECH.
- Call FastAPI through typed API helper functions.

Expected backend responsibilities:

- Receive uploaded files.
- Extract document text.
- Query the correct FAISS knowledge base.
- Run Groq-powered review or audit calls.
- Return structured JSON that React can render.
- Later support background jobs for long-running FDA audits.
- Poll FDA audit job status instead of waiting on one long request.

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file for any required API keys or local configuration.

## Run The App

Run the Streamlit prototype:

```powershell
streamlit run app.py
```

Run the FastAPI backend:

```powershell
.\venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Add New PDFs

Place privacy source PDFs in:

```text
data/privacy/raw/
```

Place FDA AI guidance PDFs in:

```text
data/fda_ai/guidance/raw/
```

Place FDA-cleared device submission PDFs in:

```text
data/fda_ai/devices/raw/
```

Then rebuild the relevant data:

```powershell
python scripts/build_knowledge_base.py privacy
python scripts/build_knowledge_base.py fda_guidance
python scripts/process_device_submissions.py
```

Restart the Streamlit app after rebuilding a FAISS index.

## Repository Notes

The repository currently includes the Version 1.0 regulatory data artifacts so the app can run with the existing HIPAA, CCPA, and HITECH knowledge base. Local environment files, virtual environments, logs, cache files, and secrets are ignored through `.gitignore`.
