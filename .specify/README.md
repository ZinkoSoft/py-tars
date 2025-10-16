# Spec-Driven Development Toolkit

This directory contains tools and templates for the Spec-Driven Development workflow used in the py-tars project.

## Overview

The Spec-Driven Development workflow helps structure feature development through a systematic approach:

1. **Specify** - Create feature specification
2. **Plan** - Generate implementation plan
3. **Tasks** - Break down into actionable tasks
4. **Implement** - Execute tasks with guidance

## Directory Structure

```
.specify/
├── README.md              # This file
├── memory/
│   └── constitution.md    # Project constitution and principles
├── scripts/
│   └── bash/
│       ├── common.sh                  # Shared functions
│       ├── check-prerequisites.sh     # Validate feature prerequisites
│       ├── create-new-feature.sh      # Initialize new feature
│       ├── implement-feature.sh       # Implementation workflow
│       ├── setup-plan.sh              # Setup planning phase
│       └── update-agent-context.sh    # Update AI agent context
└── templates/
    ├── agent-file-template.md         # AI agent configuration
    ├── checklist-template.md          # Feature checklist
    ├── plan-template.md               # Implementation plan
    ├── spec-template.md               # Feature specification
    └── tasks-template.md              # Task breakdown

```

## Workflow Commands

### 1. /speckit.specify - Create Feature Specification

**Purpose**: Initialize a new feature with its specification structure.

**Usage**:
```bash
# Create new feature directory and spec template
./.specify/scripts/bash/create-new-feature.sh
```

**Output**: Creates `specs/###-feature-name/` with:
- `spec.md` - Feature specification
- `plan.md` (placeholder)
- Directory structure for contracts, research, etc.

### 2. /speckit.plan - Generate Implementation Plan

**Purpose**: Create detailed implementation plan from specification.

**Usage**:
```bash
# Generate implementation plan (typically done via AI agent)
./.specify/scripts/bash/setup-plan.sh
```

**Output**: Fills in `plan.md` with:
- Technical context (language, frameworks, dependencies)
- Constitution compliance check
- Project structure
- Phase breakdown (Research → Design → Tasks)

### 3. /speckit.tasks - Break Down Into Tasks

**Purpose**: Generate actionable task list from implementation plan.

**Prerequisites**: 
- `plan.md` must exist
- `spec.md` with user stories recommended

**Output**: Creates `tasks.md` with:
- Tasks grouped by phase
- Task IDs (T001, T002, etc.)
- Parallel work indicators [P]
- User story mapping [US1], [US2], etc.

### 4. /speckit.implement - Implementation Workflow

**Purpose**: Guide implementation of tasks from tasks.md.

**Prerequisites**:
- `plan.md` must exist
- `tasks.md` must exist

**Usage**:
```bash
# Show default summary and next tasks
./.specify/scripts/bash/implement-feature.sh

# Show next actionable tasks
./.specify/scripts/bash/implement-feature.sh --next

# Show tasks for specific phase
./.specify/scripts/bash/implement-feature.sh --phase 2

# Show all tasks with status
./.specify/scripts/bash/implement-feature.sh --all

# Show context for specific task
./.specify/scripts/bash/implement-feature.sh --context T015

# Get help
./.specify/scripts/bash/implement-feature.sh --help
```

**Features**:
- **Next Tasks**: Shows uncompleted tasks ready to implement
- **Phase View**: Filter tasks by implementation phase
- **Task Context**: Display relevant documentation for a task
- **Progress Tracking**: Mark tasks complete by changing `[ ]` to `[X]` in tasks.md
- **Parallel Indicators**: Highlights tasks that can run in parallel

**Example Output**:
```
Feature: 002-esp32-micropython-servo
Directory: /home/runner/work/py-tars/py-tars/specs/002-esp32-micropython-servo

=== Implementation Status ===

Total tasks: 243
Completed: 5
Remaining: 238

=== Next Tasks to Implement ===

      T006 (Phase 2): Create firmware/esp32_test/pca9685.py with PCA9685 class skeleton
      T007 (Phase 2): Implement PCA9685.__init__(i2c, address=0x40)
  [P] T026 (Phase 3): [P] [US1] Create servo_controller.py with ServoController class
...

💡 Tips:
  - Use --context <ID> to see details for a specific task
  - Use --phase <N> to see all tasks in a phase
  - Mark tasks complete in tasks.md: [ ] → [X]
```

**Task Context Example**:
```bash
$ ./.specify/scripts/bash/implement-feature.sh --context T026

=== Task Context: T026 ===

Task: [P] [US1] Create firmware/esp32_test/servo_controller.py with ServoController class skeleton
Phase: 3
Status: ○ Pending
Parallel: Yes

=== Relevant Documentation ===

Plan: /path/to/specs/002-esp32-micropython-servo/plan.md
Spec: /path/to/specs/002-esp32-micropython-servo/spec.md
Research: /path/to/specs/002-esp32-micropython-servo/research.md
Data Model: /path/to/specs/002-esp32-micropython-servo/data-model.md
Contracts: /path/to/specs/002-esp32-micropython-servo/contracts
Quickstart: /path/to/specs/002-esp32-micropython-servo/quickstart.md

Use these files to understand the context and requirements for implementing this task.
```

## Feature Branch Naming

Feature branches must follow the naming convention: `###-feature-name`

Examples:
- `001-standardize-app-structures`
- `002-esp32-micropython-servo`
- `003-add-new-mcp-tool`

The number prefix corresponds to the directory name in `specs/###-feature-name/`.

## Environment Variables

### SPECIFY_FEATURE

Override the feature branch detection:

```bash
SPECIFY_FEATURE="002-esp32-micropython-servo" bash ./.specify/scripts/bash/implement-feature.sh
```

Useful for:
- Non-git repositories
- Testing scripts
- CI/CD environments

## Script Functions

### common.sh

Shared functions used by all scripts:

- `get_repo_root()` - Get repository root directory
- `get_current_branch()` - Get current feature branch
- `get_feature_paths()` - Export all feature-related paths
- `check_feature_branch()` - Validate branch naming convention

### check-prerequisites.sh

Validate feature prerequisites:

```bash
# Check basic prerequisites (plan.md required)
./check-prerequisites.sh --json

# Check implementation prerequisites (plan.md + tasks.md required)
./check-prerequisites.sh --json --require-tasks --include-tasks

# Get feature paths only (no validation)
./check-prerequisites.sh --paths-only
```

### update-agent-context.sh

Update AI agent context files with project information:

```bash
# Update all existing agent files
./update-agent-context.sh

# Update specific agent (claude, gemini, copilot, cursor, etc.)
./update-agent-context.sh claude
```

Supported agents:
- Claude (CLAUDE.md)
- Gemini (GEMINI.md)
- GitHub Copilot (.github/copilot-instructions.md)
- Cursor (.cursor/rules/specify-rules.mdc)
- And others...

## Integration with AI Agents

The `/speckit.*` commands are designed to work with AI coding agents:

1. Agent receives `/speckit.implement` command
2. Agent executes `implement-feature.sh` to see next tasks
3. Agent uses `--context <ID>` to understand task requirements
4. Agent implements the task
5. Agent marks task complete in tasks.md
6. Repeat from step 2

This workflow ensures:
- ✅ Systematic feature development
- ✅ Clear task boundaries
- ✅ Traceable progress
- ✅ Documentation consistency
- ✅ Constitution compliance

## Constitution

The `.specify/memory/constitution.md` file defines the core principles and standards for the py-tars project:

- Event-Driven Architecture (MQTT-based communication)
- Typed Contracts (Pydantic models)
- Async-First Concurrency (asyncio)
- Test-First Development
- Configuration via Environment
- Observability & Health Monitoring
- Simplicity & YAGNI

All features must comply with constitution principles. The `plan.md` includes a constitution check section.

## Templates

Templates provide consistent structure for feature documentation:

- **spec-template.md** - User stories, acceptance criteria, constraints
- **plan-template.md** - Technical context, phases, structure
- **tasks-template.md** - Actionable tasks grouped by phase/story
- **agent-file-template.md** - AI agent configuration
- **checklist-template.md** - Feature checklist

## Tips for Implementation

1. **Start with --next**: Always check what tasks are ready to implement
2. **Use --context**: Understand task requirements before coding
3. **Mark Progress**: Update tasks.md as you complete tasks
4. **Parallel Work**: Look for [P] indicators for tasks that can run in parallel
5. **Phase by Phase**: Complete phases sequentially for best results
6. **Test Early**: Run tests after implementing related tasks
7. **Stay Aligned**: Refer to plan.md and spec.md frequently

## Example Workflow

```bash
# 1. Check what's next
$ ./implement-feature.sh --next

# 2. Get context for first task
$ ./implement-feature.sh --context T006

# 3. Review relevant documentation
$ cat specs/002-esp32-micropython-servo/plan.md
$ cat specs/002-esp32-micropython-servo/data-model.md

# 4. Implement the task
$ vim firmware/esp32_test/pca9685.py

# 5. Test the implementation
$ python -m pytest tests/

# 6. Mark task complete
$ vim specs/002-esp32-micropython-servo/tasks.md
# Change: - [ ] T006 ...
# To:     - [X] T006 ...

# 7. Repeat
$ ./implement-feature.sh --next
```

## Troubleshooting

### "Not on a feature branch"

Ensure you're on a branch matching `###-feature-name` pattern or set `SPECIFY_FEATURE` environment variable.

### "plan.md not found"

Run `/speckit.plan` first to generate the implementation plan.

### "tasks.md not found"

Run `/speckit.tasks` first to generate the task breakdown.

### "Task not found in tasks.md"

Verify the task ID exists in tasks.md. Task IDs follow format: T001, T002, etc.

## Contributing

When adding new scripts or templates:

1. Follow existing naming conventions
2. Use common.sh for shared functions
3. Add help text (--help flag)
4. Support JSON output where applicable
5. Update this README
6. Test with multiple features

## License

Part of the py-tars project. See repository root for license information.
