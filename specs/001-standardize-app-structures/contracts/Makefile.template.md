# Makefile Template for py-tars Apps

This template provides standard build automation for all py-tars applications.

## Usage

Copy this template to each app directory and customize the `PACKAGE_NAME` variable.

```makefile
# Makefile for <APP_NAME>
# Standard build automation for py-tars applications

# Configuration
PACKAGE_NAME := <package_name>
SRC_DIR := src/$(PACKAGE_NAME)
TEST_DIR := tests

# Python interpreter (use configured Python environment)
PYTHON := python3

.PHONY: help fmt lint test check build clean install install-dev

help:
	@echo "Available targets:"
	@echo "  make fmt         - Format code with ruff and black"
	@echo "  make lint        - Lint with ruff and type-check with mypy"
	@echo "  make test        - Run tests with coverage"
	@echo "  make check       - Run fmt + lint + test (CI gate)"
	@echo "  make build       - Build Python package"
	@echo "  make clean       - Remove build artifacts and cache"
	@echo "  make install     - Install package in editable mode"
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
```

## Variable Customization

For each app, update:

```makefile
PACKAGE_NAME := <package_name>  # e.g., llm_worker, stt_worker, router
```

## Target Descriptions

### `make help`
Displays available targets and their descriptions.

### `make fmt`
Formats code using:
- **ruff** - Auto-fixes linting issues
- **black** - Code formatting (line-length=100)

### `make lint`
Lints and type-checks code using:
- **ruff** - Fast Python linter (replaces flake8, isort, etc.)
- **mypy** - Static type checking

### `make test`
Runs tests with:
- **pytest** - Test framework
- **pytest-cov** - Coverage reporting
- **pytest-asyncio** - Async test support

Outputs:
- Terminal coverage report
- `coverage.xml` for CI integration

### `make check`
Runs all quality gates in sequence:
1. Format code
2. Lint and type-check
3. Run tests

This is the primary CI gate target.

### `make build`
Builds distributable package using `python -m build`.

Creates:
- `dist/<package>-<version>.tar.gz` (source distribution)
- `dist/<package>-<version>-py3-none-any.whl` (wheel)

### `make clean`
Removes all build artifacts and caches:
- `__pycache__/` directories
- `.pyc`, `.pyo` files
- `.egg-info/` directories
- `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- `dist/`, `build/`
- Coverage reports

### `make install`
Installs package in editable mode (`pip install -e .`).

Use for local development and testing.

### `make install-dev`
Installs package with development dependencies (`pip install -e ".[dev]"`).

Includes:
- pytest and pytest-asyncio
- ruff, black, mypy
- Other dev tools

## Integration with CI/CD

In CI pipelines, use:

```bash
make check
```

This ensures:
1. Code is formatted correctly
2. No linting or type errors
3. All tests pass with adequate coverage

## Integration with Docker

Docker builds should:

1. Copy source code:
   ```dockerfile
   COPY src/ /app/src/
   COPY pyproject.toml /app/
   ```

2. Install package:
   ```dockerfile
   RUN pip install -e /app
   ```

The Makefile is primarily for local development; Docker builds use pip directly.

## Pre-commit Hook

To run checks automatically on commit, add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
make check
```

Or use pre-commit framework:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: make-check
        name: make check
        entry: make check
        language: system
        pass_filenames: false
```

## Troubleshooting

### "Command not found: ruff/black/mypy"
Install dev dependencies:
```bash
make install-dev
```

### "No tests found"
Ensure test files are named `test_*.py` and located in `tests/` directory.

### "Import errors during tests"
Install package in editable mode:
```bash
make install
```

### "Coverage too low"
Add more tests or adjust coverage settings in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "--cov-fail-under=80"
```
