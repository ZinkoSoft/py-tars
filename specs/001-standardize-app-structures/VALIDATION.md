# Validation Checklist for App Standardization

Use this checklist to validate each app migration before marking it complete.

## Pre-Migration Checklist

- [ ] Current structure documented in `structure-before.txt`
- [ ] Backup of current code exists (git commit)
- [ ] Understand app's MQTT topics and environment variables

## Directory Structure Validation

- [ ] `src/<package_name>/` directory exists
- [ ] `src/<package_name>/__init__.py` exists
- [ ] `src/<package_name>/__main__.py` exists (entry point)
- [ ] `src/<package_name>/config.py` exists (configuration parsing)
- [ ] `tests/` directory exists
- [ ] `tests/unit/` subdirectory exists
- [ ] `tests/integration/` subdirectory exists
- [ ] `tests/contract/` subdirectory exists
- [ ] `tests/conftest.py` exists
- [ ] No source files remain at app root (except setup files)

## Configuration Files Validation

- [ ] `pyproject.toml` exists with all required sections
- [ ] `pyproject.toml` [build-system] section present
- [ ] `pyproject.toml` [project] section with name, version, dependencies
- [ ] `pyproject.toml` [project.optional-dependencies] dev section
- [ ] `pyproject.toml` [project.scripts] entry point defined
- [ ] `pyproject.toml` [tool.setuptools] with `package-dir = {"": "src"}`
- [ ] `pyproject.toml` [tool.ruff] configured (line-length = 100)
- [ ] `pyproject.toml` [tool.black] configured (line-length = 100)
- [ ] `pyproject.toml` [tool.mypy] configured (python_version = "3.11")
- [ ] `pyproject.toml` [tool.pytest.ini_options] configured
- [ ] `Makefile` exists with all required targets
- [ ] `Makefile` has correct PACKAGE_NAME variable
- [ ] `README.md` exists with all required sections
- [ ] `.env.example` exists with all environment variables

## Makefile Targets Validation

Run each target to verify:

- [ ] `make fmt` runs successfully (formats code)
- [ ] `make lint` runs successfully (lints code, no errors)
- [ ] `make test` runs successfully (if tests exist)
- [ ] `make check` runs successfully (all quality checks pass)
- [ ] `make build` runs successfully (builds package)
- [ ] `make clean` runs successfully (removes artifacts)
- [ ] `make install` runs successfully (installs package)
- [ ] `make install-dev` runs successfully (installs with dev deps)

## Installation Validation

- [ ] `pip install -e .` succeeds without errors
- [ ] Package appears in `pip list`
- [ ] CLI entry point works: `tars-<app-name> --help`
- [ ] Can import package: `python -c "import <package_name>"`

## Code Quality Validation

- [ ] `ruff check src/<package_name>` passes
- [ ] `black --check src/<package_name>` passes
- [ ] `mypy src/<package_name>` passes (or has acceptable warnings)
- [ ] All tests pass: `pytest tests/`

## Documentation Validation

README.md must include:

- [ ] Title and description
- [ ] Installation section
- [ ] Usage section
- [ ] Configuration section (all environment variables)
- [ ] Architecture section
- [ ] MQTT Topics section (subscribed topics)
- [ ] MQTT Topics section (published topics)
- [ ] Development section (make targets)
- [ ] Troubleshooting section

.env.example must include:

- [ ] MQTT_URL
- [ ] All app-specific environment variables
- [ ] Comments explaining each variable
- [ ] Example values provided

## Docker Integration Validation (if applicable)

- [ ] Dockerfile updated for src/ layout
- [ ] Dockerfile copies src/ directory correctly
- [ ] Dockerfile installs package with `pip install -e .`
- [ ] Docker build succeeds: `docker compose build <service>`
- [ ] Docker run succeeds: `docker compose up <service>`
- [ ] Service connects to MQTT broker
- [ ] Service functions correctly in Docker

## Functional Validation

- [ ] App starts without errors
- [ ] App connects to MQTT broker
- [ ] App subscribes to correct topics
- [ ] App publishes to correct topics
- [ ] App responds to test messages
- [ ] Existing functionality preserved (no regressions)
- [ ] Configuration via environment variables works

## Integration Validation

- [ ] App works with other services in Docker stack
- [ ] MQTT messages flow correctly between services
- [ ] Full stack test passes: `docker compose up`

## Post-Migration Checklist

- [ ] New structure documented in `structure-after.txt`
- [ ] Git diff reviewed for correctness
- [ ] Changes committed with descriptive message
- [ ] No breaking changes introduced
- [ ] Performance unchanged (no regressions)

## Final Sign-Off

- [ ] All validation items above are checked
- [ ] App passes `make check`
- [ ] App builds successfully in Docker
- [ ] App functions correctly in integration
- [ ] Documentation is complete and accurate
- [ ] Migration can be considered COMPLETE

---

## Notes

- If any validation item fails, fix the issue before marking migration complete
- Document any deviations from standard structure in app's README
- Keep a record of migration time for future estimates
- Report any issues with templates or process for improvement

## Common Issues and Solutions

### Import Errors

**Issue**: Can't import package after moving to src/  
**Solution**: Run `pip install -e .` to install in editable mode

### Test Discovery Issues

**Issue**: pytest can't find tests  
**Solution**: Ensure `testpaths = ["tests"]` in pyproject.toml

### Type Check Failures

**Issue**: mypy reports many errors  
**Solution**: Add `ignore_missing_imports = true` for third-party libs without stubs

### Docker Build Failures

**Issue**: Docker can't find modules  
**Solution**: Ensure Dockerfile copies `src/` and runs `pip install -e .`

### CLI Entry Point Not Working

**Issue**: `tars-<app-name>` command not found  
**Solution**: Check `[project.scripts]` in pyproject.toml and reinstall

---

**Version**: 1.0  
**Last Updated**: 2025-10-13
