---
title: ATS Insight Backend
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# ATS-Insight Smart Resume Analyzer

An ML-powered resume analysis tool that scores resumes against job descriptions using a fine-tuned SentenceTransformer model (all-MiniLM-L6-v2), Groq LLM (Llama-3.3-70b), and spaCy NLP.

## Architecture

```
Frontend (Streamlit :8501) ──► Backend (FastAPI :8000) ──► Fine-tuned SentenceTransformer
                                          │                    (384-dim, CosineSimilarityLoss)
                                          ├──► Groq LLM (resume parsing)
                                          ├──► spaCy NLP (entity extraction)
                                          └──► Supabase (auth + history storage)
```

## Quick Start (Local)

### Prerequisites
- Python 3.11+ with a virtual environment (the project uses `venv/`)
- All dependencies: `pip install -r requirements.txt`
- spaCy model (optional, sm is auto-used as fallback): `venv\Scripts\python -m spacy download en_core_web_md`

### 1. Configure `.env`

Create (or verify) `backend/.env`:
```env
GROQ_API_KEY=gsk_...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service_role_key>
SUPABASE_ANON_KEY=<anon_key>
AUTH_REDIRECT_URL=http://localhost:8501
DEV_AUTH_BYPASS=true      # set to false in production
```

### 2. Start the Backend

```powershell
# From the repo root — ALWAYS use the venv, not system Python
.\start_backend.ps1
```

Or manually:
```powershell
venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at **http://localhost:8000**  
Swagger UI: **http://localhost:8000/docs**

### 3. Start the Frontend

In a separate terminal:
```powershell
.\start_frontend.ps1
```

Or manually:
```powershell
venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Frontend runs at **http://localhost:8501**

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/analyze-resume` | Upload resume (PDF/DOCX) + optional JD text |
| GET  | `/api/v1/health` | Health check — confirms models are loaded |
| GET  | `/api/v1/history` | Fetch signed-in user's analysis history |
| DELETE | `/api/v1/history/{id}` | Delete a history entry |
| POST | `/api/v1/generate-pdf` | Generate PDF report |

All routes (except `/health`) require `Authorization: Bearer <token>` header.  
Set `DEV_AUTH_BYPASS=true` in `.env` to skip auth during development.

---

## Fine-Tuned Model

- **Location**: `backend/ml_models/finetuned_resume_jd_model/`
- **Base model**: `all-MiniLM-L6-v2`
- **Training**: 500 Resume-JD pairs, 3 epochs, CosineSimilarityLoss
- **Metrics**: Finetuned MAE=0.149 vs Base MAE=0.205 (27% improvement)
- **Correlation**: 0.754 (finetuned) vs 0.640 (base)

The model is automatically loaded at startup — no manual configuration needed.

---

## Deployment Notes

### Backend — Hugging Face Spaces (Live)
- **URL**: https://likitha-chowdary-ats-insight-backend.hf.space
- **Swagger UI**: https://likitha-chowdary-ats-insight-backend.hf.space/docs
- **Health check**: https://likitha-chowdary-ats-insight-backend.hf.space/api/v1/health
- Set all secrets in HF Space Settings → Secrets (not Variables):
  `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_ANON_KEY`, `DEV_AUTH_BYPASS=false`, `ALLOWED_ORIGINS`

### Frontend — Streamlit Cloud (Live)
- **URL**: https://ats-insight-smart-resume-analyzer-7dahjnfufzyr96i39qnqvt.streamlit.app
- Set secrets in Streamlit App → Settings → Secrets:
  ```toml
  [supabase]
  SUPABASE_URL      = "https://fjsluiqgpxlosxovkxee.supabase.co"
  SUPABASE_ANON_KEY = "<anon_key>"

  [google_oauth]
  redirect_uri = "https://ats-insight-smart-resume-analyzer-7dahjnfufzyr96i39qnqvt.streamlit.app"

  [backend]
  url = "https://likitha-chowdary-ats-insight-backend.hf.space"
  ```

### Google OAuth Setup
For Google sign-in to work in production:
1. **Google Cloud Console** → APIs & Services → Credentials → OAuth 2.0 Client:
   - Authorized redirect URIs: `https://fjsluiqgpxlosxovkxee.supabase.co/auth/v1/callback`
   - Authorized JavaScript origins: `https://ats-insight-smart-resume-analyzer-7dahjnfufzyr96i39qnqvt.streamlit.app`
2. **Supabase** → Authentication → URL Configuration:
   - Site URL: `https://ats-insight-smart-resume-analyzer-7dahjnfufzyr96i39qnqvt.streamlit.app`
   - Redirect URLs: `https://ats-insight-smart-resume-analyzer-7dahjnfufzyr96i39qnqvt.streamlit.app`

---

## Project Structure

```
├── backend/
│   ├── api/
│   │   ├── auth.py              # JWT verification (Supabase)
│   │   └── routes.py            # FastAPI route handlers
│   ├── core/
│   │   └── config.py            # All config/env vars
│   ├── database/
│   │   └── supabase_db.py       # Async Supabase REST client
│   ├── ml_models/
│   │   └── finetuned_resume_jd_model/  # Fine-tuned SentenceTransformer
│   ├── models/
│   │   └── schemas.py           # Pydantic response models
│   ├── services/
│   │   ├── ats_scorer.py        # Score calculation
│   │   ├── feedback_engine.py   # Detailed issue generation
│   │   ├── groq_parser.py       # Async Groq LLM resume/JD parser
│   │   ├── jd_matcher.py        # JD semantic similarity
│   │   ├── model_loader.py      # SentenceTransformer loader
│   │   ├── resume_analyzer.py   # Main analysis pipeline (async)
│   │   └── resume_parser.py     # PDF/DOCX text extraction
│   └── main.py                  # FastAPI app + lifespan
├── frontend/
│   ├── components/              # Streamlit UI components
│   ├── services/
│   │   ├── api_client.py        # Backend HTTP client
│   │   └── supabase_client.py   # Auth client
│   ├── views/                   # Page views (scorer, history, landing)
│   └── streamlit_app.py         # Main Streamlit entry point
├── requirements.txt
├── start_backend.ps1            # Backend startup script (uses venv)
└── start_frontend.ps1           # Frontend startup script (uses venv)
```
