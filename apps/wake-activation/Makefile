# Makefile for wake-activation
PACKAGE_NAME := wake_activation
SRC_DIR := src/$(PACKAGE_NAME)
TEST_DIR := tests
PYTHON := python3

.PHONY: help fmt lint test check build clean install install-dev

help:
	@echo "Available targets:"
	@echo "  make fmt         - Format code"
	@echo "  make lint        - Lint and type-check"
	@echo "  make test        - Run tests"
	@echo "  make check       - Run all checks (CI gate)"
	@echo "  make build       - Build package"
	@echo "  make clean       - Remove artifacts"
	@echo "  make install     - Install in editable mode"
	@echo "  make install-dev - Install with dev dependencies"

fmt:
	@echo "🎨 Formatting code..."
	@ruff check --fix $(SRC_DIR) $(TEST_DIR) || true
	@black $(SRC_DIR) $(TEST_DIR)
	@echo "✅ Formatting complete"

lint:
	@echo "🔍 Linting code..."
	@ruff check $(SRC_DIR) $(TEST_DIR)
	@echo "🔍 Type checking..."
	@mypy $(SRC_DIR)
	@echo "✅ Linting complete"

test:
	@echo "🧪 Running tests..."
	@pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing --cov-report=xml
	@echo "✅ Tests complete"

check: fmt lint test
	@echo "✅ All checks passed!"

build:
	@echo "📦 Building package..."
	@$(PYTHON) -m build
	@echo "✅ Build complete"

clean:
	@echo "🧹 Cleaning artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ .coverage coverage.xml htmlcov/
	@echo "✅ Clean complete"

install:
	@echo "📥 Installing package..."
	@pip install -e .
	@echo "✅ Installation complete"

install-dev:
	@echo "📥 Installing package with dev dependencies..."
	@pip install -e ".[dev]"
	@echo "✅ Installation complete"
