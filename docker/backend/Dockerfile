# syntax=docker/dockerfile:1
# ---------- build stage: compilers, pip, model download (none of this ships) ----------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Bake the embedding model into the image so the first request never downloads it.
ENV FASTEMBED_CACHE_PATH=/opt/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

# ---------- runtime stage ----------
FROM python:3.12-slim

# libpq5 for psycopg2/asyncpg-adjacent tooling; no compilers, no curl.
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --user-group --home-dir /app --no-create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/opt/models \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /opt/models /opt/models

WORKDIR /app
# .dockerignore keeps every .env file (secrets) out of this copy.
COPY --chown=app:app backend /app
COPY --chown=app:app ai /app/ai

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD ["python", "-c", "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)"]

# Production default: ONE uvicorn process, no --reload, honours $PORT (Render/Railway/Fly inject it).
# Keep it single-process on purpose (no --workers, no gunicorn): the in-app auto-close loop and the
# in-memory chatbot rate limit assume exactly one process. Scale by changing those first.
# docker-compose.yml overrides this with --reload for development.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
