# Data Model: App Structure Standardization

**Date**: 2025-10-13  
**Feature**: Standardize App Folder Structures

## Overview

This document defines the standardized structure for each app in the `/apps/` directory. This is a structural refactor, not a data model for runtime entities.

## App Structure Entity

Each app follows this standardized structure:

### Directory Structure

```
apps/<app-name>/
├── Makefile                      # Build automation
├── README.md                     # Documentation
├── pyproject.toml               # Package configuration
├── .env.example                 # Configuration template
├── src/                         # Source code
│   └── <package_name>/          # Main package
│       ├── __init__.py          # Package initialization
│       ├── __main__.py          # CLI entry point
│       ├── config.py            # Configuration parsing
│       ├── service.py           # Core business logic
│       ├── models.py            # Pydantic models (optional)
│       └── ...                  # Other modules
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── conftest.py             # pytest fixtures
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── contract/               # MQTT contract tests
└── docs/                       # Additional docs (optional)
```

### File Specifications

#### Makefile

**Purpose**: Build automation and developer workflow  
**Required Targets**:
- `fmt` - Format code with ruff and black
- `lint` - Lint with ruff and type-check with mypy
- `test` - Run pytest with coverage
- `check` - Run fmt + lint + test (CI gate)
- `build` - Build Python package
- `clean` - Remove build artifacts
- `install` - Install package in editable mode
- `install-dev` - Install with dev dependencies

**Variables**:
- `PACKAGE_NAME` - Python package name
- `SRC_DIR` - Source directory path
- `TEST_DIR` - Test directory path

#### pyproject.toml

**Purpose**: Python package configuration (PEP 517/518)  
**Required Sections**:
- `[build-system]` - Build backend (setuptools)
- `[project]` - Package metadata, dependencies
- `[project.optional-dependencies]` - Dev dependencies
- `[project.scripts]` - CLI entry points
- `[tool.setuptools]` - Package directory configuration
- `[tool.ruff]` - Linter configuration
- `[tool.black]` - Formatter configuration
- `[tool.mypy]` - Type checker configuration
- `[tool.pytest.ini_options]` - Test configuration

**Key Fields**:
- `name` - Package name (format: `tars-<app-name>`)
- `version` - Semantic version (e.g., `0.1.0`)
- `requires-python` - Python version constraint (`>=3.11`)
- `dependencies` - Runtime dependencies
- `[project.scripts]` - CLI command mapping

#### README.md

**Purpose**: App documentation  
**Required Sections**:
1. **Title and Description** - App name and purpose
2. **Installation** - How to install the app
3. **Usage** - How to run the app
4. **Configuration** - Environment variables
5. **Development** - Developer workflow
6. **Architecture** - High-level design
7. **MQTT Topics** - Subscribed and published topics

#### .env.example

**Purpose**: Configuration template  
**Contents**: All environment variables with example/default values  
**Format**: `KEY=value` with comments

#### src/<package_name>/__init__.py

**Purpose**: Package initialization  
**Contents**: 
- Package version (if applicable)
- Public API exports (if applicable)
- Usually minimal or empty

#### src/<package_name>/__main__.py

**Purpose**: CLI entry point  
**Contents**:
- `main()` function that starts the service
- Command-line argument parsing (if applicable)
- Entry point for `python -m <package_name>` and console script

#### src/<package_name>/config.py

**Purpose**: Configuration management  
**Contents**:
- Parse environment variables
- Validate configuration
- Provide typed configuration objects
- Fail fast on missing required config

#### tests/conftest.py

**Purpose**: Shared pytest fixtures  
**Contents**:
- MQTT client fixtures
- Async event loop configuration
- Mock fixtures
- Test data factories

## App Inventory

### Current State Assessment

| App | Has pyproject.toml | Has tests/ | Has README | Needs Migration |
|-----|-------------------|-----------|-----------|----------------|
| camera-service | ❌ | ❌ | ✅ | 🔴 High |
| llm-worker | ✅ | ✅ | ✅ | 🟡 Medium |
| mcp-bridge | ✅ | ✅ | ✅ | 🟡 Medium |
| mcp-server | ? | ? | ? | ? |
| memory-worker | ✅ | ✅ | ✅ | 🟡 Medium |
| movement-service | ? | ? | ? | ? |
| router | ✅ | ✅ | ❌ | 🟡 Medium |
| stt-worker | ✅ | ✅ | ✅ | 🟡 Medium |
| tts-worker | ✅ | ✅ | ✅ | 🟡 Medium |
| ui | ? | ? | ? | ? |
| ui-web | ? | ? | ? | ? |
| voice | ? | ? | ? | ? |
| wake-activation | ? | ? | ? | ? |

### Migration Priority

**Priority 1 (Core Services)**:
1. stt-worker
2. router
3. llm-worker
4. memory-worker
5. tts-worker

**Priority 2 (Supporting Services)**:
6. wake-activation
7. mcp-bridge
8. camera-service
9. movement-service

**Priority 3 (UI/Other)**:
10. ui
11. ui-web
12. voice
13. mcp-server

## Migration State Transitions

Each app progresses through these states:

1. **Not Started** - Current inconsistent structure
2. **Analyzed** - Current structure documented
3. **Planned** - Migration tasks identified
4. **In Progress** - Actively migrating
5. **Testing** - Running `make check`, verifying Docker build
6. **Complete** - Passes all checks, documented
7. **Verified** - Tested in integration with other services

## Validation Rules

### Directory Structure
- ✅ Must have `src/<package_name>/` directory
- ✅ Must have `tests/` directory
- ✅ Must have `Makefile` with all required targets
- ✅ Must have `pyproject.toml` with all required sections
- ✅ Must have `README.md` with all required sections

### Package Configuration
- ✅ `pyproject.toml` must specify `requires-python = ">=3.11"`
- ✅ Must use `package-dir = {"": "src"}` for src layout
- ✅ Must include dev dependencies in `[project.optional-dependencies]`
- ✅ Must configure ruff, black, mypy, pytest tools

### Tests
- ✅ Must have `tests/conftest.py` for shared fixtures
- ✅ Must organize into `unit/`, `integration/`, `contract/` subdirectories
- ✅ All tests must pass with `pytest tests/`

### Makefile
- ✅ All required targets must be present and functional
- ✅ `make check` must pass before migration considered complete
- ✅ Must use `.PHONY` declarations for targets

### Documentation
- ✅ README.md must document all MQTT topics
- ✅ .env.example must include all environment variables
- ✅ README.md must document development workflow

## Relationships

### App Dependencies

Apps depend on:
- **packages/tars-core** - Shared utilities (if applicable)
- **MQTT Broker** - Communication infrastructure
- **Other apps** - Via MQTT topics (loose coupling)

### Docker Integration

Each app's Dockerfile must:
- Copy src/ directory
- Install package with `pip install -e .`
- Set working directory appropriately
- Preserve entry point functionality

## Non-Functional Requirements

### Performance
- No runtime performance impact (structural change only)
- Docker build time should be similar or faster (better caching)

### Compatibility
- Must maintain same import paths for external consumers
- Must work with existing Docker Compose configurations
- Must preserve all environment variable names

### Maintainability
- Consistent structure reduces cognitive load
- Standard Makefile targets improve developer experience
- Clear test organization improves test maintenance

## Success Metrics

1. **Consistency**: All 13 apps follow identical structure
2. **Completeness**: All apps have Makefile, pyproject.toml, README, tests/
3. **Quality**: All apps pass `make check`
4. **Documentation**: All apps document MQTT contracts in README
5. **Integration**: All apps build and run in Docker successfully
