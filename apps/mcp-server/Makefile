.PHONY: fmt lint test check clean run help

PACKAGE_NAME := tars_mcp_server
PYTHON := python
# Detect venv or use system python
VENV_PATH := $(shell pwd)/../../.venv/bin/python
ifneq ($(wildcard $(VENV_PATH)),)
	PYTHON := $(VENV_PATH)
endif

help:
	@echo "Available targets:"
	@echo "  fmt     - Format code with ruff and black"
	@echo "  lint    - Run ruff linter and mypy type checker"
	@echo "  test    - Run pytest with coverage"
	@echo "  check   - Run fmt, lint, and test (CI gate)"
	@echo "  clean   - Remove build artifacts and cache"
	@echo "  run     - Run the MCP server with stdio transport"

fmt:
	@echo "Running ruff import sort and format..."
	$(PYTHON) -m ruff check --select I --fix src tests
	@echo "Running black..."
	$(PYTHON) -m black src tests
	@echo "Format complete ✅"

lint:
	@echo "Running ruff linter..."
	$(PYTHON) -m ruff check src tests
	@echo "Running mypy type checker..."
	$(PYTHON) -m mypy src
	@echo "Lint complete ✅"

test:
	@echo "Running pytest..."
	$(PYTHON) -m pytest
	@echo "Tests complete ✅"

check: fmt lint test
	@echo "All checks passed ✅"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete ✅"

run:
	@echo "Starting TARS MCP Server (stdio)..."
	$(PYTHON) -m $(PACKAGE_NAME) stdio
