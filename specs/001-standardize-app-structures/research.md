# Research: App Structure Standardization

**Date**: 2025-10-13  
**Feature**: Standardize App Folder Structures

## Research Tasks

### 1. Python Packaging Best Practices (PEP 517/518)

**Decision**: Use pyproject.toml with setuptools backend and src layout

**Rationale**:
- **PEP 517/518**: Modern standard for Python packaging, replacing setup.py
- **Src layout**: Prevents accidental imports from local directory during development
- **Setuptools**: Widely adopted, stable, supports editable installs
- **Version management**: Use setuptools-scm or explicit version in pyproject.toml
- **Dependencies**: Separate `dependencies` (runtime) from `optional-dependencies.dev` (development)

**Alternatives considered**:
- **Flat layout** (package at root): More prone to import errors during development
- **Poetry**: Adds another tool dependency; setuptools is sufficient and already in use
- **Flit**: Simpler but less flexible for complex dependencies

**References**:
- https://packaging.python.org/en/latest/tutorials/packaging-projects/
- https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
- https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure

### 2. Makefile Targets for Python Projects

**Decision**: Standard targets - fmt, lint, test, check, build, clean, install

**Rationale**:
- **Consistency**: All apps use same command interface
- **CI/CD**: `make check` as single gate for CI pipelines
- **Developer UX**: Familiar interface across all apps
- **Tool agnostic**: Makefile abstracts underlying tools (ruff, black, mypy, pytest)
- **Incremental adoption**: Developers can run individual targets (fmt, lint) or all (check)

**Standard targets**:
```makefile
fmt:        # Format code (black, ruff --fix)
lint:       # Lint and type-check (ruff, mypy)
test:       # Run tests with coverage (pytest)
check:      # Run fmt + lint + test (CI gate)
build:      # Build Python package
clean:      # Remove artifacts (.pyc, __pycache__, dist/, .pytest_cache/)
install:    # Install package in editable mode
install-dev: # Install with dev dependencies
```

**Alternatives considered**:
- **tox**: More complex, slower, unnecessary for single Python version
- **nox**: Similar to tox, adds complexity
- **Just CLI tasks**: Less familiar to Python developers
- **Shell scripts**: Less portable, harder to maintain

**References**:
- https://venthur.de/2021-03-31-python-makefiles.html
- https://github.com/audreyfeldroy/cookiecutter-pypackage

### 3. Test Directory Structure

**Decision**: tests/ with unit/, integration/, contract/ subdirectories

**Rationale**:
- **Separation of concerns**: Different test types have different execution characteristics
- **Selective running**: `pytest tests/unit` vs `pytest tests/integration`
- **Contract tests**: MQTT message validation lives in contract/
- **Mirrors src/**: Easy to find corresponding tests
- **conftest.py**: Shared fixtures at tests/ root

**Structure**:
```
tests/
├── conftest.py          # Shared fixtures (MQTT client, async event loop)
├── unit/                # Fast, isolated tests
│   └── test_*.py
├── integration/         # Cross-component tests (may need MQTT broker)
│   └── test_*.py
└── contract/            # MQTT message schema validation
    └── test_*.py
```

**Alternatives considered**:
- **Flat tests/**: Harder to run subsets, mixes fast and slow tests
- **tests/ alongside src/**: Less clear separation
- **Feature-based structure**: Harder to run all unit tests at once

**References**:
- https://docs.pytest.org/en/stable/goodpractices.html#tests-outside-application-code

### 4. Migration Strategy for Existing Apps

**Decision**: Incremental app-by-app migration with backward compatibility

**Rationale**:
- **Risk management**: One app at a time, easy to rollback
- **Testing**: Verify each app works before moving to next
- **Docker compatibility**: Update Dockerfiles to handle src/ layout
- **Import preservation**: Maintain same import paths (e.g., `from llm_worker import ...`)

**Migration steps per app**:
1. Create src/<package>/ directory
2. Move existing package code to src/<package>/
3. Update pyproject.toml with `package-dir = {"": "src"}`
4. Create Makefile with standard targets
5. Organize tests into unit/, integration/, contract/
6. Update Dockerfile if present (COPY src/, install from src/)
7. Run `make check` to verify
8. Update README.md with new structure

**Docker considerations**:
- Most apps use `COPY . /app` then `pip install -e .`
- With src layout, this still works (pyproject.toml defines package location)
- Alternative: `COPY src/ /app/src/` for explicit control

**Alternatives considered**:
- **Big bang migration**: Too risky, harder to debug
- **Separate branches per app**: Merge conflicts, coordination overhead
- **New apps only**: Technical debt grows, inconsistency remains

### 5. Makefile Template

**Decision**: Parameterized Makefile template with PACKAGE_NAME variable

**Template**:
```makefile
# Makefile for <APP_NAME>
PACKAGE_NAME := <package_name>
SRC_DIR := src/$(PACKAGE_NAME)
TEST_DIR := tests

.PHONY: fmt lint test check build clean install install-dev

fmt:
	@echo "Formatting code..."
	ruff check --fix $(SRC_DIR) $(TEST_DIR)
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
```

**Rationale**:
- **Single source of truth**: All apps use same targets
- **Parameterized**: PACKAGE_NAME adapts to each app
- **Verbose output**: Clear feedback on what's running
- **Error tolerant**: `|| true` for clean commands that may fail
- **Idempotent**: Can run multiple times safely

### 6. pyproject.toml Template

**Decision**: Standard pyproject.toml with setuptools backend

**Template**:
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tars-<app-name>"
version = "0.1.0"
description = "<App description>"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  # Runtime dependencies
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "black>=24.0",
  "ruff>=0.5",
  "mypy>=1.10",
]

[project.scripts]
tars-<app-name> = "<package_name>.__main__:main"

[tool.setuptools]
package-dir = {"" = "src"}
packages = ["<package_name>"]

[tool.ruff]
line-length = 100

[tool.black]
line-length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers"
```

**Rationale**:
- **Complete configuration**: All tools configured in one file
- **Dev dependencies**: Separate from runtime for smaller production installs
- **CLI entry point**: `project.scripts` creates console command
- **Tool configs**: ruff, black, mypy, pytest all in one place
- **Strict typing**: mypy strict mode enforced

### 7. README.md Template

**Decision**: Standardized README with sections for setup, usage, development

**Template**:
```markdown
# <App Name>

<Brief description>

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

<How to run the app>

## Configuration

Environment variables:
- `VAR_NAME` - Description (default: value)
- ...

See `.env.example` for complete list.

## Development

### Running tests
```bash
make test
```

### Formatting and linting
```bash
make check
```

### Available Make targets
- `make fmt` - Format code
- `make lint` - Lint and type-check
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build package
- `make clean` - Remove artifacts

## Architecture

<Brief description of app architecture, key modules, MQTT topics>

## MQTT Topics

### Subscribed
- `topic/name` - Description

### Published
- `topic/name` - Description
```

**Rationale**:
- **Consistency**: All apps document same sections
- **Developer onboarding**: Clear instructions for setup and development
- **MQTT contracts**: Documents pub/sub topics for reference
- **Make targets**: Discoverable commands

## Conclusion

All research complete. Ready to proceed to Phase 1 (Design & Contracts).

**Key decisions**:
1. ✅ pyproject.toml with setuptools and src layout
2. ✅ Standard Makefile with 8 targets
3. ✅ tests/ with unit/, integration/, contract/ subdirectories
4. ✅ Incremental migration strategy
5. ✅ Parameterized templates for Makefile, pyproject.toml, README.md
