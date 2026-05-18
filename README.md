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

The current data pipeline is organized under `data/`:

```text
data/raw/          Source regulatory PDFs
data/extracted/    Extracted text from PDFs
data/cleaned/      Cleaned text files
data/chunked/      Chunked text used for retrieval
data/embeddings/   Generated embedding JSON
data/faiss_index/  FAISS index and metadata
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

Place new source PDFs in:

```text
data/raw/
```

Then rebuild the retrieval data:

```powershell
python scripts/extract_text.py
python scripts/clean_text.py
python scripts/chunk_text.py
python scripts/create_embeddings.py
python scripts/store_faiss.py
```

Restart the Streamlit app after rebuilding the FAISS index.

## Repository Notes

The repository currently includes the Version 1.0 regulatory data artifacts so the app can run with the existing HIPAA, CCPA, and HITECH knowledge base. Local environment files, virtual environments, logs, cache files, and secrets are ignored through `.gitignore`.
