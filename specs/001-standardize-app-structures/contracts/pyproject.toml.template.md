# pyproject.toml Template for py-tars Apps

This template provides standard Python packaging configuration for all py-tars applications.

## Full Template

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tars-<app-name>"
version = "0.1.0"
description = "<Brief description of the app>"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  # Core dependencies (all apps)
  "asyncio-mqtt>=0.16.2",
  "paho-mqtt<2.0",
  "orjson>=3.10.7",
  "pydantic>=2.6.0",
  
  # App-specific dependencies
  # Add your runtime dependencies here
]

[project.optional-dependencies]
dev = [
  # Testing
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  
  # Code quality
  "black>=24.0",
  "ruff>=0.5",
  "mypy>=1.10",
  
  # Type stubs (if needed)
  "types-orjson>=3.6",
]

[project.scripts]
tars-<app-name> = "<package_name>.__main__:main"

[tool.setuptools]
package-dir = {"" = "src"}
packages = ["<package_name>"]

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
  "DTZ",  # flake8-datetimez
  "T10",  # flake8-debugger
  "EM",   # flake8-errmsg
  "ISC",  # flake8-implicit-str-concat
  "RET",  # flake8-return
  "SIM",  # flake8-simplify
  "TID",  # flake8-tidy-imports
  "ARG",  # flake8-unused-arguments
  "PTH",  # flake8-use-pathlib
  "PL",   # pylint
  "RUF",  # ruff-specific rules
]
ignore = [
  "E501",    # line too long (handled by black)
  "PLR0913", # too many arguments
  "PLR2004", # magic value comparison
]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_unimported = false
disallow_any_generics = true
disallow_subclassing_any = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
follow_imports = "normal"
ignore_missing_imports = false

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
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

## Customization Guide

### Required Changes

For each app, update:

1. **`[project] name`**
   ```toml
   name = "tars-<app-name>"  # e.g., "tars-llm-worker"
   ```

2. **`[project] description`**
   ```toml
   description = "<Brief description>"  # e.g., "LLM worker for TARS voice assistant"
   ```

3. **`[project.scripts]`**
   ```toml
   tars-<app-name> = "<package_name>.__main__:main"
   # e.g., tars-llm-worker = "llm_worker.__main__:main"
   ```

4. **`[tool.setuptools] packages`**
   ```toml
   packages = ["<package_name>"]  # e.g., ["llm_worker"]
   ```
   
   For packages with submodules:
   ```toml
   packages = ["<package_name>", "<package_name>.submodule"]
   # e.g., ["llm_worker", "llm_worker.providers"]
   ```

5. **`[project] dependencies`**
   Add app-specific runtime dependencies:
   ```toml
   dependencies = [
     # Core (keep these)
     "asyncio-mqtt>=0.16.2",
     "paho-mqtt<2.0",
     "orjson>=3.10.7",
     "pydantic>=2.6.0",
     
     # App-specific (add yours)
     "httpx>=0.27.0",  # for HTTP clients
     "faster-whisper>=1.0.3",  # for STT worker
     "numpy>=1.26.0,<2.0",  # for audio processing
   ]
   ```

### Optional Sections

#### Multiple Packages

If your app has subpackages, list them explicitly:

```toml
[tool.setuptools]
package-dir = {"" = "src"}
packages = [
  "llm_worker",
  "llm_worker.providers",
  "llm_worker.models",
]
```

Or use `find` directive:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["<package_name>*"]
```

#### Package Data

To include non-Python files:

```toml
[tool.setuptools.package-data]
<package_name> = ["*.json", "*.txt", "data/*"]
```

#### Entry Points (Multiple Commands)

For multiple CLI commands:

```toml
[project.scripts]
tars-<app>-main = "<package>.__main__:main"
tars-<app>-tool = "<package>.cli:tool_command"
```

#### Extra Dependencies

For optional features:

```toml
[project.optional-dependencies]
dev = [...]  # Development tools (required)
ws = ["websockets>=12.0"]  # Optional websocket support
openai = ["httpx>=0.27.0"]  # Optional OpenAI support
```

Install with: `pip install -e ".[ws,openai]"`

## Tool Configuration Explained

### Ruff (Linter)

```toml
[tool.ruff]
line-length = 100  # Match black
target-version = "py311"  # Python 3.11 syntax
```

**Lint rules**:
- **E/W**: PEP 8 style errors and warnings
- **F**: Pyflakes (undefined names, unused imports)
- **I**: Isort (import sorting)
- **B**: Bugbear (common bugs and design issues)
- **PL**: Pylint (code quality checks)
- **RUF**: Ruff-specific rules

**Ignored rules**:
- **E501**: Line length (black handles this)
- **PLR0913**: Too many function arguments (sometimes necessary)
- **PLR2004**: Magic value comparison (sometimes acceptable)

### Black (Formatter)

```toml
[tool.black]
line-length = 100  # Matches py-tars standard
target-version = ["py311"]  # Python 3.11 syntax
```

### Mypy (Type Checker)

```toml
[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true  # All functions must be typed
```

**Strict mode enabled**:
- No untyped function definitions
- No untyped function calls
- No implicit `Optional`
- Warn on unused ignores

**Test relaxation**:
```toml
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # Tests can be less strict
```

### Pytest (Test Framework)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Automatic async test detection
testpaths = ["tests"]  # Where to find tests
```

**Test markers**:
- `@pytest.mark.unit` - Fast, isolated tests
- `@pytest.mark.integration` - Tests requiring external services
- `@pytest.mark.contract` - MQTT schema validation tests

Run specific markers:
```bash
pytest -m unit  # Only unit tests
pytest -m "not integration"  # Skip integration tests
```

## Validation

After creating `pyproject.toml`, verify:

### 1. Package installs
```bash
pip install -e .
```

### 2. Entry point works
```bash
tars-<app-name> --help
```

### 3. Tests run
```bash
pytest
```

### 4. Type checking passes
```bash
mypy src/<package_name>
```

### 5. Linting passes
```bash
ruff check src/<package_name>
```

### 6. Build succeeds
```bash
python -m build
```

## Common Issues

### "Package not found"
Ensure `packages` list matches actual directory name in `src/`:
```toml
packages = ["llm_worker"]  # Must match src/llm_worker/
```

### "Import errors in tests"
Install package in editable mode:
```bash
pip install -e .
```

### "Mypy can't find module"
Add to `[tool.mypy]`:
```toml
[[tool.mypy.overrides]]
module = "problematic_module"
ignore_missing_imports = true
```

### "Ruff conflicts with black"
Ensure `line-length` matches in both:
```toml
[tool.ruff]
line-length = 100

[tool.black]
line-length = 100
```

## Migration from requirements.txt

If app currently uses `requirements.txt`:

1. Copy dependencies to `[project] dependencies`
2. Copy dev dependencies to `[project.optional-dependencies] dev`
3. Pin versions as needed:
   ```toml
   dependencies = [
     "package>=1.0.0",  # Minimum version
     "package>=1.0.0,<2.0",  # Version range
     "package==1.2.3",  # Exact version (avoid unless necessary)
   ]
   ```
4. Keep `requirements.txt` for Docker (optional):
   ```bash
   pip install -e .  # Preferred in Docker
   # OR
   pip install -r requirements.txt  # If you want to keep it
   ```

## References

- [PEP 517](https://peps.python.org/pep-0517/) - Build system specification
- [PEP 518](https://peps.python.org/pep-0518/) - pyproject.toml specification
- [Setuptools documentation](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html)
- [Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
