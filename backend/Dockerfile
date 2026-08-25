FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt /app/backend/requirements.txt
COPY ingestion/requirements.txt /app/ingestion/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt -r /app/ingestion/requirements.txt

# Pre-download the nomic embedding model at build time so container startup requires 0 download and 0 extra RAM
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='nomic-ai/nomic-embed-text-v1.5', threads=1)"

# Copy application code
COPY backend/ /app/backend/
COPY ingestion/ /app/ingestion/

# Expose port
EXPOSE 8000

# Run with uvicorn honoring $PORT
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
