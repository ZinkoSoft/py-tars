# Makefile for config-manager service
# Standard targets for TARS project

PACKAGE_NAME = config_manager

.PHONY: fmt lint test check clean install

# Format code with black and ruff
fmt:
	@echo "Formatting code..."
	@ruff check --fix src/ tests/ || true
	@black src/ tests/

# Lint code with ruff and mypy
lint:
	@echo "Linting code..."
	@ruff check src/ tests/
	@mypy src/

# Run tests with pytest
test:
	@echo "Running tests..."
	@pytest

# Run all checks (fmt + lint + test) - CI gate
check: fmt lint test
	@echo "All checks passed!"

# Clean build artifacts and cache
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -f .coverage coverage.xml

# Install package in editable mode with dev dependencies
install:
	@echo "Installing package in editable mode..."
	@pip install -e .[dev]
