.PHONY: help fmt lint test check clean run

PACKAGE_NAME := mcp_bridge
PYTHON := python

help:
	@echo "Available targets:"
	@echo "  fmt    - Format code with black and ruff"
	@echo "  lint   - Run ruff and mypy checks"
	@echo "  test   - Run pytest tests"
	@echo "  check  - Run fmt, lint, and test (CI pipeline)"
	@echo "  clean  - Remove build artifacts and caches"
	@echo "  run    - Run mcp-bridge build script"

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
	rm -rf build dist *.egg-info
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete ✅"

run:
	@echo "Running MCP bridge build script..."
	$(PYTHON) -m $(PACKAGE_NAME)
