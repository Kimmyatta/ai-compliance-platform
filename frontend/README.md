# AI Compliance Platform Frontend

React + TypeScript frontend for the AI Compliance Platform.

The frontend is separate from Streamlit. Streamlit can continue to run as the local prototype, while this app becomes the browser UI for the FastAPI backend.

## Architecture

```text
React + TypeScript frontend
        |
        v
FastAPI backend at http://127.0.0.1:8000
        |
        v
Python review and audit services
```

## Run Locally

Install Node.js first. Then from `frontend/`:

```powershell
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The FastAPI backend should also be running:

```powershell
.\venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

If the frontend shows `API offline` while FastAPI works in the terminal, make sure the backend CORS setting includes the frontend origin:

```text
http://127.0.0.1:5173
```

## Environment

By default, the frontend calls:

```text
http://127.0.0.1:8000
```

To point it somewhere else, create `frontend/.env`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Current Pages

```text
FDA AI Device Audit
Privacy Review
Audit History
```

The FDA page uses the FastAPI background job endpoints:

```text
POST /api/fda-audit/jobs/upload
POST /api/fda-audit/jobs/devices/{filename}
GET  /api/fda-audit/jobs/{job_id}
```
