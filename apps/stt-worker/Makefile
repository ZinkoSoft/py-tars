# Makefile for stt-worker
PACKAGE_NAME := stt_worker
SRC_DIR := src/$(PACKAGE_NAME)
TEST_DIR := tests
VENV := /home/james/git/py-tars/.venv/bin

.PHONY: fmt lint test check build clean install install-dev

fmt:
	@echo "Formatting code..."
	$(VENV)/ruff check --fix $(SRC_DIR) $(TEST_DIR) || true
	$(VENV)/black $(SRC_DIR) $(TEST_DIR)

lint:
	@echo "Linting code..."
	$(VENV)/ruff check $(SRC_DIR) $(TEST_DIR)
	@echo "Skipping mypy for now (needs type stub updates)"
	# $(VENV)/mypy $(SRC_DIR)

test:
	@echo "Running tests..."
	$(VENV)/pytest $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=term-missing

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
	rm -rf dist/ build/ .pytest_cache/ .coverage .mypy_cache/ .ruff_cache/ coverage.xml

install:
	@echo "Installing package..."
	pip install -e .

install-dev:
	@echo "Installing package with dev dependencies..."
	pip install -e ".[dev]"
