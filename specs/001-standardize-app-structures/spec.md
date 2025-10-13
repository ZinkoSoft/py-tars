# Feature Specification: Standardize App Folder Structures

**Date**: 2025-10-13  
**Status**: Planning

## Overview

Standardize all applications under `/apps/` to follow Python best practices and expected file structures. Each app should be structured as if it were a standalone Python project with consistent conventions, tooling, and Makefiles.

## Goals

1. **Consistency**: All apps follow the same directory structure and organization patterns
2. **Best Practices**: Align with Python community standards (PEP 517/518, src layout, etc.)
3. **Developer Experience**: Each app can be developed, tested, and built independently
4. **Tooling**: Each app has a Makefile with standard targets (fmt, lint, test, check, build)
5. **Maintainability**: Clear separation of source, tests, configuration, and documentation

## Current State

Apps have inconsistent structures:
- Some have `main.py` at root (stt-worker, router, tts-worker)
- Some use package name directories (llm-worker has `llm_worker/`, memory-worker has `memory_worker/`)
- Some have README.md, others don't
- Some have pyproject.toml, others use requirements.txt
- No standardized Makefile across apps
- Inconsistent test directory structures
- camera-service lacks proper Python packaging entirely

## Proposed Structure

Each app under `/apps/<app-name>/` should follow this structure:

```
apps/<app-name>/
├── Makefile                    # Standard targets: fmt, lint, test, check, build, clean
├── README.md                   # App-specific documentation
├── pyproject.toml             # Python packaging configuration (PEP 517/518)
├── .env.example               # Example environment variables
├── src/                       # Source code (src layout pattern)
│   └── <package_name>/        # Main package
│       ├── __init__.py
│       ├── __main__.py        # Entry point (if CLI app)
│       ├── config.py          # Configuration parsing
│       ├── service.py         # Core business logic
│       └── ...                # Other modules
├── tests/                     # Test directory mirroring src/
│   ├── __init__.py
│   ├── conftest.py           # pytest fixtures
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── contract/             # MQTT contract tests
└── docs/                     # Additional documentation (optional)
```

### Standard Makefile Targets

Each Makefile should provide:
- `make fmt` - Format code with ruff and black
- `make lint` - Lint with ruff and type-check with mypy
- `make test` - Run pytest with coverage
- `make check` - Run fmt + lint + test (CI gate)
- `make build` - Build Python package
- `make clean` - Remove build artifacts and cache files
- `make install` - Install package in editable mode
- `make install-dev` - Install with dev dependencies

## Apps to Standardize

1. **camera-service** - Needs complete packaging setup
2. **llm-worker** - Mostly good, needs Makefile and src/ layout
3. **mcp-bridge** - Needs Makefile and src/ layout
4. **mcp-server** - Needs review
5. **memory-worker** - Needs Makefile and src/ layout
6. **movement-service** - Needs review
7. **router** - Needs packaging, Makefile, and src/ layout
8. **stt-worker** - Needs Makefile and src/ layout
9. **tts-worker** - Needs Makefile and src/ layout
10. **ui** - Needs review
11. **ui-web** - Needs review
12. **voice** - Needs review
13. **wake-activation** - Needs review

## Non-Goals

- Do not change the functionality or behavior of any app
- Do not modify MQTT contracts or message payloads
- Do not refactor business logic
- Do not change Docker configurations (separate concern)

## Success Criteria

1. All apps have consistent directory structure with src/ layout
2. All apps have pyproject.toml (no standalone requirements.txt)
3. All apps have Makefile with standard targets
4. All apps have README.md with basic documentation
5. All apps can be installed with `pip install -e .`
6. All apps pass `make check` successfully
7. Documentation updated to reflect new structure

## Constraints

- Must maintain Python 3.11+ compatibility
- Must preserve all existing functionality
- Must not break Docker builds
- Must not change MQTT contracts
- Changes must be backward compatible for existing deployments
