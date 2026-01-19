.PHONY: help dev up down logs build migrate test clean

help:
	@echo "Sage - AI Executive Assistant"
	@echo ""
	@echo "Usage:"
	@echo "  make dev       - Start all services in development mode"
	@echo "  make up        - Start all services in detached mode"
	@echo "  make down      - Stop all services"
	@echo "  make logs      - View logs from all services"
	@echo "  make build     - Rebuild all containers"
	@echo "  make migrate   - Run database migrations"
	@echo "  make test      - Run tests"
	@echo "  make clean     - Remove all containers and volumes"
	@echo "  make prod      - Start with production profile (Cloudflare tunnel)"

# Development
dev:
	docker compose up

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

# Database
migrate:
	docker compose exec backend alembic upgrade head

migrate-new:
	@read -p "Migration name: " name; \
	docker compose exec backend alembic revision --autogenerate -m "$$name"

# Testing
test:
	docker compose exec backend pytest

test-cov:
	docker compose exec backend pytest --cov=sage --cov-report=html

# Cleanup
clean:
	docker compose down -v --remove-orphans

# Production (with Cloudflare tunnel)
prod:
	docker compose --profile production up -d

# Backend shell
shell:
	docker compose exec backend python -c "from sage.main import app; import asyncio"

# Database shell
db-shell:
	docker compose exec postgres psql -U sage -d sage

# Redis CLI
redis-cli:
	docker compose exec redis redis-cli

# Backup
backup:
	./scripts/backup.sh

# Initial setup
setup:
	./scripts/setup.sh
