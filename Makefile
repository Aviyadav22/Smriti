.PHONY: dev test lint migrate ingest clean health

# Start all infrastructure services
infra:
	docker compose up -d

# Start backend dev server
backend:
	cd backend && uvicorn app.main:app --reload --port 8000

# Run backend tests
test:
	cd backend && pytest -v --cov=app

# Run unit tests only
test-unit:
	cd backend && pytest tests/unit/ -v

# Run integration tests
test-integration:
	cd backend && pytest tests/integration/ -v -m integration

# Run security tests
test-security:
	cd backend && pytest tests/security/ -v -m security

# Run linters
lint:
	cd backend && ruff check . && mypy app/

# Format code
format:
	cd backend && ruff format .

# Run database migrations
migrate:
	cd backend && alembic upgrade head

# Create new migration
migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# Ingest SC judgments for one year
ingest:
	cd backend && python scripts/ingest_s3.py --year $(year)

# Ingest all available years
ingest-all:
	cd backend && python scripts/ingest_s3.py --all

# Clean local data
clean:
	docker compose down -v
	rm -rf backend/data/raw/*
	rm -rf backend/data/extracted/*
	rm -rf backend/data/pdfs/*
	rm -f backend/data/ingestion_tracker.db

# Health check
health:
	curl -s http://localhost:8000/health | python -m json.tool
