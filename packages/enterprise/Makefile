# Fastband Enterprise Control Plane Makefile

.PHONY: all build test lint clean run help

# Build variables
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME := $(shell date -u '+%Y-%m-%dT%H:%M:%SZ')
LDFLAGS := -ldflags "-X main.Version=$(VERSION)"

# Go variables
GOCMD := go
GOBUILD := $(GOCMD) build
GOTEST := $(GOCMD) test
GOMOD := $(GOCMD) mod

# Binary output
BINARY := fastband-enterprise
BINARY_PATH := bin/$(BINARY)

## help: Show this help message
help:
	@echo "Fastband Enterprise Control Plane"
	@echo ""
	@echo "Usage:"
	@echo "  make <target>"
	@echo ""
	@echo "Targets:"
	@sed -n 's/^##//p' $(MAKEFILE_LIST) | column -t -s ':' | sed -e 's/^/ /'

## all: Build and test
all: build test lint

## build: Build the binary
build:
	@echo "Building $(BINARY)..."
	@mkdir -p bin
	$(GOBUILD) $(LDFLAGS) -o $(BINARY_PATH) ./cmd/fastband-enterprise

## test: Run all tests
test:
	@echo "Running tests..."
	$(GOTEST) -v -race ./...

## test-cover: Run tests with coverage
test-cover:
	@echo "Running tests with coverage..."
	$(GOTEST) -v -race -coverprofile=coverage.out ./...
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

## lint: Run golangci-lint
lint:
	@echo "Running linter..."
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run; \
	else \
		echo "golangci-lint not installed, skipping..."; \
		echo "Install with: go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"; \
	fi

## fmt: Format code
fmt:
	@echo "Formatting code..."
	$(GOCMD) fmt ./...

## vet: Run go vet
vet:
	@echo "Running go vet..."
	$(GOCMD) vet ./...

## tidy: Tidy go modules
tidy:
	@echo "Tidying modules..."
	$(GOMOD) tidy

## clean: Clean build artifacts
clean:
	@echo "Cleaning..."
	@rm -rf bin/
	@rm -f coverage.out coverage.html

## run: Run the server (requires FASTBAND_AUTH_SECRET)
run: build
	@if [ -z "$(FASTBAND_AUTH_SECRET)" ]; then \
		echo "Error: FASTBAND_AUTH_SECRET environment variable is required"; \
		echo "Usage: FASTBAND_AUTH_SECRET=your-secret make run"; \
		exit 1; \
	fi
	./$(BINARY_PATH)

## run-dev: Run with example secret (for development only)
run-dev: build
	@echo "WARNING: Using development secret - DO NOT USE IN PRODUCTION"
	FASTBAND_AUTH_SECRET=dev-secret-do-not-use-in-production \
		FASTBAND_LISTEN_ADDR=:8080 \
		./$(BINARY_PATH)

## verify-fail-closed: Verify fail-closed behavior
verify-fail-closed: build
	@echo "Testing fail-closed behavior (should fail to start)..."
	@unset FASTBAND_AUTH_SECRET && \
		timeout 2 ./$(BINARY_PATH) 2>&1 || \
		if [ $$? -eq 1 ]; then \
			echo "PASS: Server correctly refused to start without auth secret"; \
		else \
			echo "FAIL: Server should have exited with code 1"; \
			exit 1; \
		fi

## verify-auth: Verify auth middleware (requires running server)
verify-auth:
	@echo "Testing auth middleware..."
	@echo "1. Testing health endpoint (no auth required)..."
	@curl -sf http://localhost:8080/healthz > /dev/null && echo "   PASS: /healthz accessible without auth" || echo "   FAIL: /healthz should be accessible"
	@echo "2. Testing API endpoint without auth (should get 401)..."
	@STATUS=$$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/v1/tickets 2>/dev/null); \
	if [ "$$STATUS" = "401" ]; then \
		echo "   PASS: /v1/tickets returns 401 without auth"; \
	else \
		echo "   FAIL: Expected 401, got $$STATUS"; \
	fi

## docker-build: Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker build -t fastband-enterprise:$(VERSION) .

## deps: Download dependencies
deps:
	@echo "Downloading dependencies..."
	$(GOMOD) download
