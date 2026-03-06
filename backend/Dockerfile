FROM python:3.12-slim

WORKDIR /app

# System dependencies for PDF processing and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first (needed for pip install .)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir .

# Cloud Run sets PORT env var
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
