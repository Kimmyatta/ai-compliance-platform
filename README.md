# AI Compliance Platform

AI Compliance Platform is a Streamlit-based compliance review assistant for regulatory documents. Version 1.0 focuses on HIPAA, CCPA, and HITECH review using local regulatory PDFs, document extraction, embeddings, and FAISS search.

The platform supports two core workflows:

- Ask compliance questions and retrieve relevant regulatory context.
- Upload documents and generate structured compliance review feedback.

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

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file for any required API keys or local configuration.

## Run The App

```powershell
streamlit run app.py
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
