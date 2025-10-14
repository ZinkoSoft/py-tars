# Makefile for movement-service
# Standard targets for formatting, linting, testing

PACKAGE_NAME := movement_service
PYTHON := python3
SRC_DIR := src
TESTS_DIR := tests

.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

.PHONY: install
install: ## Install package in editable mode with dev dependencies
	$(PYTHON) -m pip install -e ".[dev]"

.PHONY: fmt
fmt: ## Format code with ruff and black
	$(PYTHON) -m ruff check --fix $(SRC_DIR) $(TESTS_DIR)
	$(PYTHON) -m black $(SRC_DIR) $(TESTS_DIR)

.PHONY: lint
lint: ## Lint code with ruff and mypy
	$(PYTHON) -m ruff check $(SRC_DIR) $(TESTS_DIR)
	$(PYTHON) -m mypy $(SRC_DIR)

.PHONY: test
test: ## Run tests with pytest
	$(PYTHON) -m pytest $(TESTS_DIR) -v

.PHONY: test-unit
test-unit: ## Run unit tests only
	$(PYTHON) -m pytest $(TESTS_DIR)/unit -v -m unit

.PHONY: test-integration
test-integration: ## Run integration tests only
	$(PYTHON) -m pytest $(TESTS_DIR)/integration -v -m integration

.PHONY: test-contract
test-contract: ## Run contract tests only
	$(PYTHON) -m pytest $(TESTS_DIR)/contract -v -m contract

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest $(TESTS_DIR) --cov=$(PACKAGE_NAME) --cov-report=term-missing --cov-report=html

.PHONY: check
check: fmt lint test ## Run all checks (format, lint, test)

.PHONY: clean
clean: ## Clean build artifacts and cache files
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.PHONY: run
run: ## Run the movement service
	$(PYTHON) -m $(PACKAGE_NAME)

.PHONY: tree
tree: ## Show project structure
	tree -I '__pycache__|*.pyc|.pytest_cache|.mypy_cache|.ruff_cache|htmlcov|*.egg-info' -a
