# Implementation Plan Summary

**Feature**: Standardize App Folder Structures  
**Branch**: `001-standardize-app-structures`  
**Status**: Phase 1 Complete - Ready for Implementation

## What Was Accomplished

### Phase 0: Research ✅
- Researched Python packaging best practices (PEP 517/518)
- Evaluated src layout vs flat layout
- Designed Makefile target standards
- Planned test directory organization
- Created migration strategy

### Phase 1: Design & Contracts ✅
- Created comprehensive data model defining standard structure
- Developed three templates:
  - **Makefile.template.md** - 8 standard targets
  - **pyproject.toml.template.md** - Complete packaging config
  - **README.template.md** - Documentation standard
- Created quickstart guide for migrations
- Updated agent context with new patterns

## Key Deliverables

All deliverables in `/home/james/git/py-tars/specs/001-standardize-app-structures/`:

1. **spec.md** - Feature specification
2. **plan.md** - This implementation plan
3. **research.md** - Research findings and decisions
4. **data-model.md** - Standard app structure definition
5. **quickstart.md** - Step-by-step migration guide
6. **contracts/** - Template files
   - Makefile.template.md
   - pyproject.toml.template.md
   - README.template.md

## Standard App Structure

Every app in `/apps/` will follow:

```
apps/<app-name>/
├── Makefile                    # Build automation
├── README.md                   # Documentation
├── pyproject.toml             # Package configuration
├── .env.example               # Configuration template
├── src/                       # Source code
│   └── <package_name>/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       └── service.py
└── tests/                     # Test suite
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── contract/
```

## Standard Makefile Targets

All apps will support:
- `make fmt` - Format code
- `make lint` - Lint and type-check
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build package
- `make clean` - Remove artifacts
- `make install` - Install in editable mode
- `make install-dev` - Install with dev dependencies

## Constitution Compliance

✅ All constitution checks pass:
- No MQTT contract changes
- No breaking changes to APIs
- Preserves all existing functionality
- Enhances maintainability and developer experience
- Follows Python community standards

## Apps to Standardize

13 apps total, recommended order:

**Priority 1 (Core Services):**
1. stt-worker
2. router
3. llm-worker
4. memory-worker
5. tts-worker

**Priority 2 (Supporting Services):**
6. wake-activation
7. mcp-bridge
8. camera-service
9. movement-service

**Priority 3 (UI/Other):**
10. ui
11. ui-web
12. voice
13. mcp-server

## Next Steps

1. **Run `/speckit.tasks`** to generate task breakdown
2. **Follow quickstart.md** for each app migration
3. **Verify each app**:
   - `make check` passes
   - Docker build succeeds
   - Integration tests pass
4. **Update main repository documentation**
5. **Configure CI to use `make check`**

## Estimated Timeline

- Simple apps: 30-60 minutes each
- Medium apps: 1-2 hours each
- Complex apps: 2-3 hours each
- **Total: 15-25 hours for all 13 apps**

## Success Criteria

Migration complete when:
- [x] ~~Phase 0: Research complete~~
- [x] ~~Phase 1: Design and templates complete~~
- [ ] Phase 2: All 13 apps standardized
- [ ] All apps pass `make check`
- [ ] All apps build in Docker
- [ ] Full stack runs successfully
- [ ] Documentation updated

## Key Design Decisions

1. **Src layout** - Prevents import errors during development
2. **pyproject.toml** - Modern Python packaging (PEP 517/518)
3. **Makefile** - Consistent developer interface
4. **Test organization** - Separate unit/integration/contract tests
5. **Templates** - Ensure consistency across all apps
6. **Incremental migration** - One app at a time, reduce risk

## Benefits

### For Developers
- Consistent structure across all apps
- Standard commands (`make check`)
- Clear separation of source and tests
- Comprehensive documentation

### For Maintainability
- Easier onboarding for new contributors
- Reduced cognitive load when switching apps
- Standard quality gates
- Better IDE support

### For CI/CD
- Single command to run all checks
- Consistent test organization
- Clear build process
- Better caching with src layout

## References

- **Spec**: `specs/001-standardize-app-structures/spec.md`
- **Research**: `specs/001-standardize-app-structures/research.md`
- **Data Model**: `specs/001-standardize-app-structures/data-model.md`
- **Quickstart**: `specs/001-standardize-app-structures/quickstart.md`
- **Templates**: `specs/001-standardize-app-structures/contracts/`

## Command to Continue

To proceed to task breakdown and implementation:

```bash
# Follow the speckit.tasks prompt (not yet run)
# This is where Phase 2 implementation would begin
```

---

**Planning Phase Complete** ✅

The `/speckit.plan` command has successfully completed Phases 0 and 1. All research, design, and templates are ready for implementation.
