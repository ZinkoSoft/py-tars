#!/usr/bin/env bash

# Implementation workflow script for Spec-Driven Development
#
# This script provides a structured workflow for implementing tasks from tasks.md.
# It helps developers navigate the implementation phase with context and guidance.
#
# MAIN FUNCTIONS:
# 1. Prerequisites Validation
#    - Verifies plan.md and tasks.md exist
#    - Validates feature directory structure
#    - Ensures implementation prerequisites are met
#
# 2. Task Display & Navigation
#    - Shows all tasks grouped by phase
#    - Highlights next actionable tasks
#    - Displays task dependencies and parallel opportunities
#
# 3. Context Provision
#    - Shows relevant sections from plan.md
#    - Displays related contracts and data models
#    - Links to research and quickstart guides
#
# 4. Implementation Guidance
#    - Suggests which tasks to tackle next
#    - Identifies parallel work opportunities
#    - Shows progress through phases
#
# Usage: ./implement-feature.sh [OPTIONS]
#
# OPTIONS:
#   --next              Show next tasks to implement
#   --phase <N>         Show tasks for specific phase
#   --all               Show all tasks with status
#   --context <ID>      Show context for specific task ID
#   --json              Output in JSON format
#   --help, -h          Show help message

set -e

# Parse command line arguments
SHOW_NEXT=false
SHOW_ALL=false
SHOW_CONTEXT=""
PHASE_FILTER=""
JSON_MODE=false

for arg in "$@"; do
    case "$arg" in
        --next)
            SHOW_NEXT=true
            ;;
        --all)
            SHOW_ALL=true
            ;;
        --phase)
            PHASE_FILTER="$2"
            shift
            ;;
        --context)
            SHOW_CONTEXT="$2"
            shift
            ;;
        --json)
            JSON_MODE=true
            ;;
        --help|-h)
            cat << 'EOF'
Usage: implement-feature.sh [OPTIONS]

Structured workflow for implementing tasks from tasks.md.

OPTIONS:
  --next              Show next tasks to implement (uncompleted, no blocking dependencies)
  --phase <N>         Show tasks for specific phase (e.g., --phase 2)
  --all               Show all tasks with completion status
  --context <ID>      Show context for specific task ID (e.g., --context T001)
  --json              Output in JSON format
  --help, -h          Show this help message

EXAMPLES:
  # Show next actionable tasks
  ./implement-feature.sh --next
  
  # Show all tasks in phase 2
  ./implement-feature.sh --phase 2
  
  # Show context for task T015
  ./implement-feature.sh --context T015
  
  # Show all tasks with status
  ./implement-feature.sh --all
  
WORKFLOW:
  1. Run with --next to see what to implement
  2. Use --context <ID> to get task details and relevant documentation
  3. Implement the task following the plan.md and contracts
  4. Mark task as complete in tasks.md by changing [ ] to [X]
  5. Repeat from step 1

EOF
            exit 0
            ;;
        *)
            if [[ "$arg" != --* ]] && [[ -z "$PHASE_FILTER" ]] && [[ -z "$SHOW_CONTEXT" ]]; then
                echo "ERROR: Unknown option '$arg'. Use --help for usage information." >&2
                exit 1
            fi
            ;;
    esac
done

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Get feature paths and validate
eval $(get_feature_paths)
check_feature_branch "$CURRENT_BRANCH" "$HAS_GIT" || exit 1

# Validate prerequisites
if [[ ! -d "$FEATURE_DIR" ]]; then
    echo "ERROR: Feature directory not found: $FEATURE_DIR" >&2
    echo "Run /speckit.specify first to create the feature structure." >&2
    exit 1
fi

if [[ ! -f "$IMPL_PLAN" ]]; then
    echo "ERROR: plan.md not found in $FEATURE_DIR" >&2
    echo "Run /speckit.plan first to create the implementation plan." >&2
    exit 1
fi

if [[ ! -f "$TASKS" ]]; then
    echo "ERROR: tasks.md not found in $FEATURE_DIR" >&2
    echo "Run /speckit.tasks first to create the task list." >&2
    exit 1
fi

# Function to extract tasks from tasks.md
extract_tasks() {
    local tasks_file="$1"
    grep -E '^[[:space:]]*-[[:space:]]+\[[[:space:]xX]\].*T[0-9]+' "$tasks_file" || true
}

# Function to check if task is complete
is_task_complete() {
    local task_line="$1"
    echo "$task_line" | grep -qE '^[[:space:]]*-[[:space:]]+\[[xX]\]'
}

# Function to extract task ID
get_task_id() {
    local task_line="$1"
    echo "$task_line" | grep -oE 'T[0-9]+' | head -1
}

# Function to extract task description
get_task_description() {
    local task_line="$1"
    echo "$task_line" | sed -E 's/^[^T]*T[0-9]+\s*//'
}

# Function to check if task can run in parallel
is_parallel_task() {
    local task_line="$1"
    echo "$task_line" | grep -qE '\[P\]'
}

# Function to extract phase from tasks.md
get_task_phase() {
    local task_id="$1"
    local tasks_file="$2"
    local current_phase=""
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^##[[:space:]]Phase[[:space:]]([0-9]+) ]]; then
            current_phase="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ $task_id ]]; then
            echo "$current_phase"
            return
        fi
    done < "$tasks_file"
    
    echo "unknown"
}

# Function to show task context
show_task_context() {
    local task_id="$1"
    local tasks_file="$TASKS"
    
    echo "=== Task Context: $task_id ==="
    echo ""
    
    # Find and display the task
    local task_line=$(grep -E "^[[:space:]]*-[[:space:]]+\[[[:space:]xX]\].*$task_id" "$tasks_file" | head -1)
    if [[ -z "$task_line" ]]; then
        echo "ERROR: Task $task_id not found in tasks.md" >&2
        return 1
    fi
    
    echo "Task: $(get_task_description "$task_line")"
    echo "Phase: $(get_task_phase "$task_id" "$tasks_file")"
    echo "Status: $(is_task_complete "$task_line" && echo "✓ Complete" || echo "○ Pending")"
    echo "Parallel: $(is_parallel_task "$task_line" && echo "Yes" || echo "No")"
    echo ""
    
    echo "=== Relevant Documentation ==="
    echo ""
    echo "Plan: $IMPL_PLAN"
    [[ -f "$FEATURE_SPEC" ]] && echo "Spec: $FEATURE_SPEC"
    [[ -f "$RESEARCH" ]] && echo "Research: $RESEARCH"
    [[ -f "$DATA_MODEL" ]] && echo "Data Model: $DATA_MODEL"
    [[ -d "$CONTRACTS_DIR" ]] && echo "Contracts: $CONTRACTS_DIR"
    [[ -f "$QUICKSTART" ]] && echo "Quickstart: $QUICKSTART"
    echo ""
    
    echo "Use these files to understand the context and requirements for implementing this task."
}

# Function to show next tasks
show_next_tasks() {
    local tasks_file="$TASKS"
    
    echo "=== Next Tasks to Implement ==="
    echo ""
    
    local has_next=false
    while IFS= read -r line; do
        if is_task_complete "$line"; then
            continue
        fi
        
        local task_id=$(get_task_id "$line")
        local description=$(get_task_description "$line")
        local phase=$(get_task_phase "$task_id" "$tasks_file")
        local parallel=$(is_parallel_task "$line" && echo "[P]" || echo "   ")
        
        echo "  $parallel $task_id (Phase $phase): $description"
        has_next=true
    done < <(extract_tasks "$tasks_file")
    
    if [[ "$has_next" == "false" ]]; then
        echo "  All tasks complete! 🎉"
    fi
    echo ""
}

# Function to show all tasks
show_all_tasks() {
    local tasks_file="$TASKS"
    
    echo "=== All Tasks ==="
    echo ""
    
    local current_phase=""
    while IFS= read -r line; do
        # Check for phase headers
        if [[ "$line" =~ ^##[[:space:]]Phase[[:space:]]([0-9]+) ]]; then
            current_phase="${BASH_REMATCH[1]}"
            echo ""
            echo "Phase $current_phase:"
            continue
        fi
        
        # Process task lines
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+\[[[:space:]xX]\].*T[0-9]+ ]]; then
            local status=$(is_task_complete "$line" && echo "✓" || echo "○")
            local task_id=$(get_task_id "$line")
            local description=$(get_task_description "$line")
            local parallel=$(is_parallel_task "$line" && echo "[P]" || echo "   ")
            
            echo "  $status $parallel $task_id: $description"
        fi
    done < "$tasks_file"
    echo ""
}

# Function to show tasks for specific phase
show_phase_tasks() {
    local phase_num="$1"
    local tasks_file="$TASKS"
    
    echo "=== Phase $phase_num Tasks ==="
    echo ""
    
    local in_phase=false
    while IFS= read -r line; do
        # Check for phase headers
        if [[ "$line" =~ ^##[[:space:]]Phase[[:space:]]([0-9]+) ]]; then
            if [[ "${BASH_REMATCH[1]}" == "$phase_num" ]]; then
                in_phase=true
            else
                in_phase=false
            fi
            continue
        fi
        
        # Process task lines in this phase
        if [[ "$in_phase" == "true" ]] && [[ "$line" =~ ^[[:space:]]*-[[:space:]]+\[[[:space:]xX]\].*T[0-9]+ ]]; then
            local status=$(is_task_complete "$line" && echo "✓" || echo "○")
            local task_id=$(get_task_id "$line")
            local description=$(get_task_description "$line")
            local parallel=$(is_parallel_task "$line" && echo "[P]" || echo "   ")
            
            echo "  $status $parallel $task_id: $description"
        fi
    done < "$tasks_file"
    echo ""
}

# Main execution
echo "Feature: $CURRENT_BRANCH"
echo "Directory: $FEATURE_DIR"
echo ""

if [[ -n "$SHOW_CONTEXT" ]]; then
    show_task_context "$SHOW_CONTEXT"
elif [[ "$SHOW_NEXT" == "true" ]]; then
    show_next_tasks
elif [[ -n "$PHASE_FILTER" ]]; then
    show_phase_tasks "$PHASE_FILTER"
elif [[ "$SHOW_ALL" == "true" ]]; then
    show_all_tasks
else
    # Default: show summary and next tasks
    echo "=== Implementation Status ==="
    echo ""
    
    # Count total and completed tasks
    total_tasks=$(extract_tasks "$TASKS" | wc -l)
    completed_tasks=$(extract_tasks "$TASKS" | grep -cE '^[[:space:]]*-[[:space:]]+\[[xX]\]' || echo 0)
    remaining_tasks=$((total_tasks - completed_tasks))
    
    echo "Total tasks: $total_tasks"
    echo "Completed: $completed_tasks"
    echo "Remaining: $remaining_tasks"
    echo ""
    
    if [[ $remaining_tasks -gt 0 ]]; then
        show_next_tasks
        echo "💡 Tips:"
        echo "  - Use --context <ID> to see details for a specific task"
        echo "  - Use --phase <N> to see all tasks in a phase"
        echo "  - Mark tasks complete in tasks.md: [ ] → [X]"
    else
        echo "All tasks complete! 🎉"
        echo ""
        echo "Next steps:"
        echo "  - Review and test your implementation"
        echo "  - Update documentation if needed"
        echo "  - Consider creating a COMPLETION_REPORT.md"
    fi
fi

exit 0
