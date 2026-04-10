---
name: "ralph"
description: "Ralph autonomous AI agent loop for iterative task completion. Invoke when user wants to automate development tasks using Ralph loop pattern, break down complex projects into small verifiable tasks, or run autonomous task execution loops."
---

# Ralph - Autonomous AI Agent Loop

Ralph is an autonomous AI agent loop for iterative task completion. It breaks down complex projects into small, verifiable tasks and executes them one by one.

## Core Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                     Ralph Loop                                   │
│                                                                 │
│  ┌─────────┐    ┌──────────┐    ┌─────────────┐                │
│  │ prd.json │ → │  Ralph   │ → │  Task Handler│                │
│  │ (tasks) │    │   Loop   │    │   (AI/Func) │                │
│  └─────────┘    └──────────┘    └─────────────┘                │
│       ↑                                    │                     │
│       └──────── progress.txt (learnings) ←┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## Ralph Principles

1. **Fresh Context Each Iteration** - Each loop starts with clean context
2. **Small Tasks** - Each task should complete in one context window
3. **Explicit Memory** - State persists via files, not model context
4. **Verification** - Quality checks (tests, typecheck) gate completion
5. **Learnings** - Record patterns/gotchas for future iterations

## Installation

This skill is self-contained. All required Python modules are in the skill directory:
- `task_state.py` - Task state management
- `tool_verifier.py` - Tool verification
- `ralph_loop.py` - Main loop implementation

## Usage

### 1. Create PRD (Task List)

Create `prd.json` with tasks structured for autonomous execution:

```json
{
  "project": "My Project",
  "tasks": [
    {
      "id": 1,
      "title": "Implement feature A",
      "description": "Create file A.py with class A",
      "status": "pending",
      "verification": "python -c 'import A; print(\"OK\")'"
    },
    {
      "id": 2,
      "title": "Implement feature B",
      "description": "Create file B.py that uses A",
      "status": "pending",
      "verification": "python -c 'from B import B; print(\"OK\")'"
    }
  ]
}
```

### 2. Run Ralph Loop

```python
from ralph_loop import RalphLoop

# Initialize
ralph = RalphLoop('prd.json')

# Set task handler (your AI/function that executes tasks)
def my_task_handler(task, context):
    # Your implementation here
    # Return (success: bool, message: str)
    return True, "Task completed"

ralph.set_task_handler(my_task_handler)

# Run the loop
summary = ralph.run()
```

### 3. Progress Tracking

Ralph automatically creates `progress.txt` with learnings:

```
=== Iteration 1 ===
Task [1]: Implement feature A
Status: Success
Message: Task completed
Timestamp: 2024-01-15T10:30:00

=== Iteration 2 ===
Task [2]: Implement feature B
Status: Failed
Message: Import error
Timestamp: 2024-01-15T10:35:00
```

## Task Structure Guidelines

### Good Tasks (Complete in One Iteration)
- "Add import pathlib to tool_verifier.py"
- "Write test for TaskState.create_task()"
- "Add __init__.py to infrastructure/"

### Bad Tasks (Too Large - Split These)
- "Implement entire agent system" (split into:感知层, 决策层, 执行层, etc.)
- "Add all middleware" (split into one per middleware)

## API Reference

### RalphLoop

Main class for running the autonomous loop.

```python
RalphLoop(
    prd_path: str,           # Path to prd.json
    progress_path: str,      # Path to progress.txt (optional)
    max_iterations: int = 50, # Max iterations (optional)
    verifier: ToolVerifier   # Custom verifier (optional)
)
```

Methods:
- `set_task_handler(handler)` - Set the function that executes tasks
- `run()` - Run the loop until completion
- `reset()` - Reset all tasks to pending
- `get_status()` - Get current status

### TaskStateManager

Manages task state persistence.

```python
TaskStateManager(prd_path: str)
```

Methods:
- `load()` - Load project state from PRD file
- `save()` - Save project state to PRD file
- `get_next_pending_task()` - Get next pending task
- `update_task(task)` - Update a task
- `get_progress()` - Get progress statistics
- `is_complete()` - Check if all tasks completed

### ToolVerifier

Verifies task completion by running commands.

```python
ToolVerifier(timeout: int = 60, cwd: str = None)
```

Methods:
- `verify(command)` - Run shell command and return result
- `verify_import(module_path)` - Verify Python import
- `verify_file_exists(file_path)` - Verify file exists
- `verify_python_syntax(file_path)` - Verify Python syntax

## Example: Complete Workflow

```python
from ralph_loop import RalphLoop, create_prd_template

# 1. Create PRD
tasks = [
    {
        "title": "Create utils module",
        "description": "Create utils.py with helper functions",
        "verification": "python -c 'import utils; print(\"OK\")'"
    },
    {
        "title": "Create main module",
        "description": "Create main.py that imports utils",
        "verification": "python -c 'from main import main; print(\"OK\")'"
    }
]
create_prd_template("My Project", tasks, "prd.json")

# 2. Define task handler
def execute_task(task, context):
    # This is where you'd call an AI or implement logic
    print(f"Executing: {task.title}")
    print(context)
    # Simulate work
    return True, "Completed"

# 3. Run Ralph
ralph = RalphLoop("prd.json")
ralph.set_task_handler(execute_task)
summary = ralph.run()

print(f"Completed {summary['completed']}/{summary['total_tasks']} tasks")
```

## Important Notes

- Ralph is designed for **small, verifiable tasks** - not large features
- Each iteration should complete in one AI call
- If a task fails 3 times, it's marked as failed (manual intervention needed)
- Always verify with concrete commands, not "looks good"
- The task handler is responsible for the actual work (calling AI, etc.)
