# Implementation Plan: Standardize App Folder Structures

**Branch**: `001-standardize-app-structures` | **Date**: 2025-10-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-standardize-app-structures/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Standardize all applications under `/apps/` to follow Python best practices with consistent directory structure (src layout), packaging (pyproject.toml), testing conventions, and Makefiles. Each app will be structured as an independent Python project with standard tooling targets (fmt, lint, test, check) while preserving all existing functionality and MQTT contracts.

## Technical Context

**Language/Version**: Python 3.11+ (required by constitution for TaskGroup, async performance, typing)  
**Primary Dependencies**: 
- Build: setuptools>=68, wheel, setuptools-scm (for version management)
- Format: black (line-length=100)
- Lint: ruff (line-length=100)
- Type Check: mypy (strict mode)
- Test: pytest>=8.2, pytest-asyncio>=0.23, pytest-cov
- App-specific: asyncio-mqtt, paho-mqtt<2.0, pydantic>=2.6, orjson>=3.10

**Storage**: N/A (structural refactor only)  
**Testing**: pytest with pytest-asyncio for async code, pytest-cov for coverage reporting  
**Target Platform**: Linux (Docker containers with host networking), Orange Pi 5 Max  
**Project Type**: Multiple independent services (13 apps) following microservices architecture  
**Performance Goals**: Zero performance impact (structural refactor only, no logic changes)  
**Constraints**: 
- Must not break existing Docker builds (apps installed via pip in containers)
- Must not change MQTT contracts or message schemas
- Must preserve all env-based configuration
- Must maintain backward compatibility for deployment
- Must pass existing tests without modification

**Scale/Scope**: 13 applications across ~15k LOC, each app 500-2000 LOC

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Event-Driven Architecture** | ✅ PASS | No changes to MQTT contracts or communication patterns |
| **II. Typed Contracts** | ✅ PASS | No changes to Pydantic models or message schemas |
| **III. Async-First Concurrency** | ✅ PASS | No changes to async patterns or concurrency logic |
| **IV. Test-First Development** | ✅ PASS | Existing tests preserved; new structural tests added for packaging |
| **V. Configuration via Environment** | ✅ PASS | No changes to environment-based configuration |
| **VI. Observability & Health** | ✅ PASS | No changes to logging, health checks, or metrics |
| **VII. Simplicity & YAGNI** | ✅ PASS | Adds necessary structure without unnecessary complexity; follows Python community standards (PEP 517/518, src layout) |

**Quality Gates**:
- ✅ No MQTT contract changes
- ✅ No breaking changes to existing APIs
- ✅ Preserves all existing functionality
- ✅ Adds standard tooling (Makefile) for developer experience
- ✅ Follows Python packaging best practices

**Conclusion**: All constitution checks pass. This is a structural improvement that enhances maintainability and developer experience without violating any core principles.

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature standardizes the structure within each app directory. The standard structure for each app is:

```
apps/<app-name>/
├── Makefile                      # Standard targets: fmt, lint, test, check, build, clean
├── README.md                     # App-specific documentation
├── pyproject.toml               # Python packaging (PEP 517/518)
├── .env.example                 # Example environment variables
├── src/                         # Source code (src layout)
│   └── <package_name>/          # Main package (e.g., llm_worker, stt_worker)
│       ├── __init__.py
│       ├── __main__.py          # Entry point for CLI apps
│       ├── config.py            # Configuration parsing from env
│       ├── service.py           # Core business logic
│       ├── models.py            # Pydantic models (if app-specific)
│       └── ...                  # Additional modules
├── tests/                       # Test directory
│   ├── __init__.py
│   ├── conftest.py             # pytest fixtures
│   ├── unit/                   # Unit tests
│   │   └── test_*.py
│   ├── integration/            # Integration tests
│   │   └── test_*.py
│   └── contract/               # MQTT contract tests
│       └── test_*.py
└── docs/                       # Additional docs (optional)
```

**Apps affected** (13 total):
- camera-service
- llm-worker
- mcp-bridge
- mcp-server
- memory-worker
- movement-service
- router
- stt-worker
- tts-worker
- ui
- ui-web
- voice
- wake-activation

**Structure Decision**: Using src layout pattern (PEP 517/518 best practice) for all apps. This provides:
1. Clear separation between source and tests
2. Prevents accidental imports from local directory during development
3. Ensures proper packaging and installation
4. Standard Python community practice
5. Consistent with existing apps/llm-worker structure

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

**No complexity violations** - This feature improves simplicity by standardizing structure.

## Implementation Status

### Phase 0: Research ✅ COMPLETE

Research document created at `research.md`:
- ✅ Python packaging best practices (PEP 517/518, src layout)
- ✅ Makefile targets standardization
- ✅ Test directory structure (unit/integration/contract)
- ✅ Migration strategy (incremental, app-by-app)
- ✅ Template designs (Makefile, pyproject.toml, README.md)

**Outcome**: All technical decisions made; ready for design phase.

### Phase 1: Design & Contracts ✅ COMPLETE

Design artifacts created:
- ✅ `data-model.md` - Standard app structure definition
- ✅ `contracts/Makefile.template.md` - Build automation template
- ✅ `contracts/pyproject.toml.template.md` - Packaging configuration template
- ✅ `contracts/README.template.md` - Documentation template
- ✅ `quickstart.md` - Migration guide for developers

**Outcome**: Complete templates and migration guide ready for implementation.

### Phase 2: Implementation (Not Started)

This phase is handled by the `/speckit.tasks` command. The planning phase ends here.

**Next Steps**:
1. Run `/speckit.tasks` to generate task breakdown
2. Execute tasks following quickstart guide
3. Migrate apps in recommended order (see quickstart.md)
4. Verify each app with `make check` and Docker build

## Re-evaluation of Constitution Check (Post-Design)

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Event-Driven Architecture** | ✅ PASS | No changes to MQTT contracts or communication |
| **II. Typed Contracts** | ✅ PASS | Templates enforce Pydantic models in pyproject.toml |
| **III. Async-First Concurrency** | ✅ PASS | No concurrency changes |
| **IV. Test-First Development** | ✅ PASS | Test structure (unit/integration/contract) enforced |
| **V. Configuration via Environment** | ✅ PASS | .env.example template ensures documentation |
| **VI. Observability & Health** | ✅ PASS | No changes to logging or health checks |
| **VII. Simplicity & YAGNI** | ✅ PASS | Adds necessary standardization without over-engineering |

**Final Assessment**: All gates pass. Design enhances consistency and maintainability without introducing complexity or violations.
