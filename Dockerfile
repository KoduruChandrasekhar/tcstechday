# PromoForge backend (FastAPI engine + the original single-file UI).
# Works on Hugging Face Spaces (Docker SDK, port 7860) and any host that sets $PORT (Render, Railway, Fly, Cloud Run).
# Needs ~500 MB RAM. Only data/synthetic is shipped: the engine never reads data/_truth.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    PROMOFORGE_DB=/tmp/promoforge.db

# Hugging Face Spaces runs containers as uid 1000
RUN useradd -m -u 1000 app
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=app backend/app backend/app
COPY --chown=app data/synthetic data/synthetic

USER app
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT} --workers 1"]
