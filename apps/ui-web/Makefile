# Makefile for ui-web
PACKAGE_NAME := ui_web
SRC_DIR := src/$(PACKAGE_NAME)
TEST_DIR := tests
FRONTEND_DIR := frontend

.PHONY: fmt lint test check build clean install install-dev
.PHONY: frontend-install frontend-dev frontend-build frontend-check frontend-clean

# Backend targets
fmt:
	@echo "Formatting backend code..."
	ruff check --fix $(SRC_DIR) $(TEST_DIR)
	black $(SRC_DIR) $(TEST_DIR)

lint:
	@echo "Linting backend code..."
	ruff check $(SRC_DIR) $(TEST_DIR)
	mypy $(SRC_DIR)

test:
	@echo "Running backend tests..."
	pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing

check: fmt lint test
	@echo "All backend checks passed!"

build:
	@echo "Building package..."
	python -m build

clean:
	@echo "Cleaning backend artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ .pytest_cache/ .coverage .mypy_cache/ .ruff_cache/

install:
	@echo "Installing package..."
	pip install -e .

install-dev:
	@echo "Installing package with dev dependencies..."
	pip install -e ".[dev]"

# Frontend targets
frontend-install:
	@echo "Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install

frontend-dev:
	@echo "Starting frontend dev server..."
	cd $(FRONTEND_DIR) && npm run dev

frontend-build:
	@echo "Building frontend for production..."
	cd $(FRONTEND_DIR) && npm run build

frontend-check:
	@echo "Running frontend checks..."
	cd $(FRONTEND_DIR) && npm run check

frontend-clean:
	@echo "Cleaning frontend artifacts..."
	cd $(FRONTEND_DIR) && rm -rf node_modules dist .vite coverage

# Combined targets
install-all: install install-dev frontend-install
	@echo "All dependencies installed!"

check-all: check frontend-check
	@echo "All checks passed (backend + frontend)!"

clean-all: clean frontend-clean
	@echo "All artifacts cleaned!"
