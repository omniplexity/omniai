# OmniAI Docker Management
# Usage: make <target>

.PHONY: help build up down restart logs clean prod dev

# Default target
help:
	@echo "OmniAI Docker Commands"
	@echo "====================="
	@echo "make up          - Start all services (production)"
	@echo "make dev         - Start services in development mode"
	@echo "make down        - Stop all services"
	@echo "make restart     - Restart all services"
	@echo "make logs        - View logs from all services"
	@echo "make clean       - Stop services and remove volumes"
	@echo "make build       - Build all images without starting"
	@echo ""

# Start production services
up:
	docker-compose up -d
	@echo "Services started. Backend: http://localhost:8000"
	@echo "Frontend (production): http://localhost:8080"

# Start development services
dev:
	docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
	@echo "Development services started."
	@echo "Backend (with reload): http://localhost:8000"
	@echo "Frontend dev server: Use 'npm run dev' in omni-web/"

# Stop all services
down:
	docker-compose down

# Restart all services
restart:
	docker-compose restart

# View logs
logs:
	docker-compose logs -f

# Clean up everything (including volumes)
clean:
	docker-compose down -v
	@echo "All volumes removed."

# Build images without starting
build:
	docker-compose build

# Build development images
build-dev:
	docker-compose -f docker-compose.yml -f docker-compose.override.yml build

# Health check
health:
	@echo "Checking backend health..."
	@curl -s http://localhost:8000/v1/system/health || echo "Backend not responding"
