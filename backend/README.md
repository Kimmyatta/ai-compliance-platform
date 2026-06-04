# AI Compliance Platform Backend

FastAPI backend for the AI Compliance Platform.

## Run Locally

From the project root:

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Then open:

```text
http://localhost:8000/docs
```

## Environment

The backend reads `GROQ_API_KEY` from `.env` in the project root or from the server environment.

Optional CORS setting:

```text
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Initial Endpoints

```text
GET  /api/health
GET  /api/fda-audit/devices
POST /api/fda-audit/upload
POST /api/fda-audit/devices/{filename}
POST /api/privacy-review/upload
```

The React frontend should call these endpoints instead of importing Python audit files directly.
