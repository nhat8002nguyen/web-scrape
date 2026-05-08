.PHONY: help build run-loader run-discovery run-submission test clean docker-build docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build all binaries
	@echo "Building domain-loader..."
	go build -o bin/domain-loader cmd/domain-loader/main.go
	@echo "Building discovery-worker..."
	go build -o bin/discovery-worker cmd/discovery-worker/main.go
	@echo "Building submission-worker..."
	go build -o bin/submission-worker cmd/submission-worker/main.go

run-loader: ## Run domain loader
	go run cmd/domain-loader/main.go --config config/config.yaml --file domains.csv

run-discovery: ## Run discovery worker
	go run cmd/discovery-worker/main.go --config config/config.yaml

run-submission: ## Run submission worker
	go run cmd/submission-worker/main.go --config config/config.yaml

test: ## Run tests
	go test -v -race -coverprofile=coverage.out ./...

test-coverage: test ## Run tests with coverage report
	go tool cover -html=coverage.out

lint: ## Run linter
	golangci-lint run ./...

clean: ## Clean build artifacts
	rm -rf bin/
	rm -f coverage.out

docker-build: ## Build Docker images
	docker build -f deployments/docker/Dockerfile.loader -t form-submission/loader:latest .
	docker build -f deployments/docker/Dockerfile.discovery -t form-submission/discovery:latest .
	docker build -f deployments/docker/Dockerfile.submission -t form-submission/submission:latest .

docker-up: ## Start all services via Docker Compose
	docker-compose -f deployments/docker/docker-compose.instance1.yml up -d

docker-down: ## Stop all services
	docker-compose -f deployments/docker/docker-compose.instance1.yml down

docker-logs: ## View Docker logs
	docker-compose -f deployments/docker/docker-compose.instance1.yml logs -f

deps: ## Download dependencies
	go mod download
	go mod tidy

migrate-up: ## Run database migrations
	psql $(shell cat config/config.yaml | grep -A5 postgres | grep database | awk '{print $$2}') < migrations/001_init_schema.sql

fmt: ## Format code
	go fmt ./...
	goimports -w .

vendor: ## Vendor dependencies
	go mod vendor
