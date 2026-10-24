# Backend image for Render (or any Docker host).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tesseract is only an offline OCR fallback for when no Gemini model is reachable.
# Everything else (PyMuPDF, Pillow, asyncpg, bcrypt ...) ships as binary wheels, so no compiler is needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=appuser:appuser app ./app
USER appuser

EXPOSE 8000
# Render injects $PORT. --proxy-headers makes uvicorn trust the X-Forwarded-* headers set by Render's load balancer.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
