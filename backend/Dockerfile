FROM python:3.12-slim

WORKDIR /app

# System dependencies for PDF processing and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Cloud Run sets PORT env var
ENV PORT=8000

EXPOSE 8000

CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
