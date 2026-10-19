FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (build-essential, curl, libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so the first request never downloads it.
ENV FASTEMBED_CACHE_PATH=/opt/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

# Copy backend application and ai package
COPY backend /app
COPY ai /app/ai

EXPOSE 8000

# Production default: no reload, and honour $PORT (Render/Railway/Fly inject it).
# docker-compose overrides this with --reload for local development.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
