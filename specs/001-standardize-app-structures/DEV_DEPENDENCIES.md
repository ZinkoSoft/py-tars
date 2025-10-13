# Shared Development Dependencies Reference

This document lists the standardized versions for development tools across all py-tars apps.

## Python Version

- **Minimum**: Python 3.11+
- **Docker Default**: Python 3.11-slim

## Core Development Tools

### Testing

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "pytest-mock>=3.12",  # Optional, for mocking
]
```

**Versions**:
- pytest: 8.2+
- pytest-asyncio: 0.23+ (for async test support)
- pytest-cov: 5.0+ (for coverage reporting)
- pytest-mock: 3.12+ (optional, for advanced mocking)

### Code Formatting

```toml
[project.optional-dependencies]
dev = [
  "black>=24.0",
  "ruff>=0.5",
]
```

**Versions**:
- black: 24.0+ (code formatter)
- ruff: 0.5+ (fast linter and import sorter)

**Configuration**:
- Line length: 100 (for both black and ruff)
- Target: Python 3.11

### Type Checking

```toml
[project.optional-dependencies]
dev = [
  "mypy>=1.10",
  "types-orjson>=3.6",  # Type stubs for orjson
]
```

**Versions**:
- mypy: 1.10+ (static type checker)
- types-orjson: 3.6+ (type stubs)

**Configuration**:
- Strict mode enabled for src/
- Relaxed for tests/

### Build Tools

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"
```

**Versions**:
- setuptools: 68+
- wheel: latest
- build: latest (for `python -m build`)

## Runtime Dependencies (Common)

These dependencies are commonly used across apps:

```toml
[project]
dependencies = [
  # MQTT
  "asyncio-mqtt>=0.16.2",
  "paho-mqtt<2.0",  # Must be <2.0 for asyncio-mqtt compatibility
  
  # JSON
  "orjson>=3.10.7",  # Fast JSON serialization
  
  # Data Validation
  "pydantic>=2.6.0",  # Data validation and models
]
```

## Tool Configuration Standards

### Ruff

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
  "E",    # pycodestyle errors
  "W",    # pycodestyle warnings
  "F",    # pyflakes
  "I",    # isort
  "N",    # pep8-naming
  "UP",   # pyupgrade
  "B",    # flake8-bugbear
  "C4",   # flake8-comprehensions
  "PTH",  # flake8-use-pathlib
  "PL",   # pylint
  "RUF",  # ruff-specific rules
]
ignore = [
  "E501",    # line too long (handled by black)
  "PLR0913", # too many arguments (sometimes necessary)
  "PLR2004", # magic value comparison
]
```

### Black

```toml
[tool.black]
line-length = 100
target-version = ["py311"]
```

### Mypy

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true  # Strict mode for src/
disallow_any_generics = true
warn_redundant_casts = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # Relaxed for tests
```

### Pytest

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Automatic async test detection
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
  "-v",
  "--strict-markers",
  "--strict-config",
  "--cov-report=term-missing",
]
markers = [
  "unit: Unit tests (fast, isolated)",
  "integration: Integration tests (may require external services)",
  "contract: MQTT contract tests (validates message schemas)",
]
```

## Makefile Targets

All apps should have these standard targets:

- `make fmt` - Format code with ruff and black
- `make lint` - Lint with ruff and type-check with mypy
- `make test` - Run pytest with coverage
- `make check` - Run fmt + lint + test (CI gate)
- `make build` - Build Python package
- `make clean` - Remove build artifacts
- `make install` - Install package in editable mode
- `make install-dev` - Install with dev dependencies

## Version Consistency Guidelines

1. **Use minimum version specifiers** (`>=`) for flexibility
2. **Pin major versions only** when necessary (e.g., `paho-mqtt<2.0`)
3. **Keep versions consistent** across all apps in the monorepo
4. **Update all apps together** when upgrading tool versions
5. **Test compatibility** before committing version changes

## Updating Versions

When updating tool versions:

1. Update this reference document first
2. Update all app pyproject.toml files
3. Run `make check` in each app to verify compatibility
4. Test full Docker stack
5. Commit all changes together

## App-Specific Dependencies

Apps may add additional dependencies beyond these core tools. Examples:

- **STT Worker**: faster-whisper, webrtcvad, numpy
- **TTS Worker**: piper-tts (or similar)
- **LLM Worker**: httpx (for API calls)
- **Memory Worker**: sentence-transformers, faiss-cpu
- **Camera Service**: opencv-python, pillow

These should be documented in each app's pyproject.toml and README.md.

---

**Version**: 1.0  
**Last Updated**: 2025-10-13  
**Python Version**: 3.11+
