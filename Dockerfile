# ── Dockerfile for HuggingFace Spaces (Docker SDK) ───────────────────────────
#
# HuggingFace Spaces gives free:
#   - 2 vCPU  (can use 4 burst)
#   - 16 GB RAM    ← handles spaCy + sentence-transformers comfortably
#   - Runs 24/7 for public spaces
#   - No credit card required
#
# Deploy steps (see README for full guide):
#   1. Create a new Space at https://huggingface.co/new-space
#   2. SDK = "Docker", Visibility = "Public"
#   3. Connect to GitHub repo OR push directly to the HF Space repo
#   4. Set Space Secrets (Settings → Variables and Secrets)

FROM python:3.13-slim

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy requirements first so Docker caches this layer (faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Download NLP models at build time ─────────────────────────────────────────
# Baking models into the image avoids slow first-request downloads
RUN python -m spacy download en_core_web_md && \
    python -m spacy download en_core_web_sm

# Pre-download sentence-transformer model weights into the image cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('Model cached OK')"

# ── Copy application code ─────────────────────────────────────────────────────
COPY . .

# ── HuggingFace Spaces configuration ─────────────────────────────────────────
# HF Spaces always uses port 7860 — do NOT change this
ENV PORT=7860
EXPOSE 7860

# Create non-root user (HF Spaces requirement)
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# ── Start FastAPI ─────────────────────────────────────────────────────────────
CMD ["python", "-m", "uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "7860", \
     "--workers", "1"]
