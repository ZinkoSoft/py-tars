# Makefile for router
PACKAGE_NAME := router
SRC_DIR := src/$(PACKAGE_NAME)
TEST_DIR := tests

.PHONY: fmt lint test check build clean install install-dev

fmt:
	@echo "Formatting code..."
	ruff check --fix $(SRC_DIR) $(TEST_DIR) || true
	black $(SRC_DIR) $(TEST_DIR)

lint:
	@echo "Linting code..."
	ruff check $(SRC_DIR) $(TEST_DIR)
	mypy $(SRC_DIR)

test:
	@echo "Running tests..."
	pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing

check: fmt lint test
	@echo "All checks passed!"

build:
	@echo "Building package..."
	python -m build

clean:
	@echo "Cleaning artifacts..."
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
