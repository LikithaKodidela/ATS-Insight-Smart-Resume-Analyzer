import os
from pathlib import Path


def _ensure_valid_ssl_cert_file():
    ssl_cert_file = os.getenv("SSL_CERT_FILE")
    if ssl_cert_file and Path(ssl_cert_file).is_file():
        return

    try:
        import certifi
    except ImportError:
        return

    certifi_path = certifi.where()
    if Path(certifi_path).is_file():
        os.environ["SSL_CERT_FILE"] = certifi_path


# Load .env from the project root (two levels up from this file) explicitly —
# load_dotenv() with no args relies on caller-frame inspection that can fail
# silently under uvicorn reload, leaving env vars unset.
try:
    from dotenv import load_dotenv
    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(_PROJECT_ROOT / '.env')
    load_dotenv(_PROJECT_ROOT / 'backend' / '.env', override=False)
except ImportError:
    pass

_ensure_valid_ssl_cert_file()

PROJECT_ROOT   = Path(__file__).resolve().parents[2]
BACKEND_DIR    = PROJECT_ROOT / "backend"
ML_MODELS_DIR  = BACKEND_DIR / "ml_models"
COLAB_DATA_DIR = PROJECT_ROOT / "colab_notebooks" / "data"

# ── API metadata ────────────────────────────────────────────────────────────
APP_TITLE       = 'ATS RESUME ANALYZER API'
APP_VERSION     = '1.0.0'
APP_DESCRIPTION = 'Analyse resumes against job descriptions using NLP + ML'

# ── CORS ────────────────────────────────────────────────────────────────────
# Add your deployed Streamlit Cloud URL here via env var (comma-separated):
#   ALLOWED_ORIGINS=https://yourapp.streamlit.app
_extra_origins = [
    o.strip() for o in os.getenv('ALLOWED_ORIGINS', '').split(',') if o.strip()
]
ALLOWED_ORIGINS = [
    "http://localhost:8501",    # Streamlit frontend (local dev)
    "http://127.0.0.1:8501",
    "http://localhost:8502",
    "http://localhost:5173",    # Vite dev server
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    *_extra_origins,            # from ALLOWED_ORIGINS env var (production)
]

# ── File upload limits ──────────────────────────────────────────────────────
MAX_FILE_SIZE_MB    = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# ── Supported MIME types ────────────────────────────────────────────────────
SUPPORTED_MIME_TYPES = {
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
}

SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx'}

# ── NLP / ML models ─────────────────────────────────────────────────────────
SPACY_MODEL_PRIMARY   = "en_core_web_md"   # better accuracy (install separately)
SPACY_MODEL_SECONDARY = "en_core_web_sm"   # fallback

SENTENCE_TRANSFORMER_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")

FINE_TUNED_MODEL_PATH = os.getenv(
    "FINE_TUNED_MODEL_PATH",
    str(ML_MODELS_DIR / "finetuned_resume_jd_model"),
)
FINE_TUNED_MODEL_FALLBACK_PATH = os.getenv(
    "FINE_TUNED_MODEL_FALLBACK_PATH",
    str(ML_MODELS_DIR / "finetuned_bert"),
)
FINE_TUNE_METADATA_PATH = os.getenv(
    "FINE_TUNE_METADATA_PATH",
    str(COLAB_DATA_DIR / "finetune_metadata.json"),
)
ALLOW_MODEL_DOWNLOADS = os.getenv("ALLOW_MODEL_DOWNLOADS", "false").lower() in {
    "1", "true", "yes",
}

# ── Score component weights ─────────────────────────────────────────────────
SCORE_WEIGHTS = {
    "formatting": 20, "keywords": 25, "content": 25,
    "skill_validation": 15, "ats_compatibility": 15,
}

JD_KEYWORD_WEIGHT = 0.6
JD_SEMANTIC_WEIGHT = 0.4

# ── Supabase / Auth ─────────────────────────────────────────────────────────
SUPABASE_URL        = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY        = os.getenv('SUPABASE_KEY', '')           # service_role — DB writes (bypasses RLS)
SUPABASE_ANON_KEY   = os.getenv('SUPABASE_ANON_KEY', '')      # public anon — frontend auth calls
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET', '')    # used by backend to verify access tokens

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

DEV_AUTH_BYPASS = os.getenv('DEV_AUTH_BYPASS', 'false').lower() in {
    '1', 'true', 'yes',
}
