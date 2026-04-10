---
name: "ralph"
description: "Ralph is an autonomous AI agent loop for iterative task completion. Invoke when user wants to automate development tasks using Ralph loop pattern."
---

# Ralph - Autonomous Agent Loop

Ralph is an AI agent loop that builds incrementally using small, verifiable tasks.

## Core Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                     Ralph Loop                                   │
│                                                                 │
│  ┌─────────┐    ┌──────────┐    ┌─────────────┐                │
│  │ prd.json │ → │  Ralph   │ → │  Fresh AI   │                │
│  │ (tasks) │    │   Loop   │    │   Instance  │                │
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

## Workflow

### 1. Create PRD (Task List)

Create `prd.json` with tasks structured for autonomous execution:

```json
{
  "project": "Project Name",
  "tasks": [
    {
      "id": 1,
      "title": "Implement task state manager",
      "description": "Create infrastructure/task_state.py with TaskState class",
      "status": "pending",
      "verification": "python -c 'from infrastructure.task_state import TaskState; print(\"OK\")'"
    },
    {
      "id": 2,
      "title": "Implement tool verifier",
      "description": "Create infrastructure/tool_verifier.py with ToolVerifier class",
      "status": "pending",
      "verification": "python -c 'from infrastructure.tool_verifier import ToolVerifier; print(\"OK\")'"
    }
  ]
}
```

### 2. Execute Ralph Loop

For each iteration:
1. Read `prd.json` - find lowest ID with `status: "pending"`
2. Build task context - include task description + all learnings
3. Execute task with fresh AI instance
4. Run verification command
5. If pass: update `prd.json` status to `done`, append to `progress.txt`
6. If fail: record error, increment retry count
7. Repeat until all tasks complete

### 3. Progress Tracking

`progress.txt` - Append-only learnings:
```
=== Iteration 3 ===
Task: Implement tool verifier
Error: Import failed - missing pathlib
Solution: Add import pathlib
Learned: Always check dependencies first

=== Iteration 4 ===
Task: Implement tool verifier
Success!
```

## Task Structure Guidelines

### Good Tasks (Complete in One Iteration)
- "Add import pathlib to tool_verifier.py"
- "Write test for TaskState.create_task()"
- "Add __init__.py to infrastructure/"

### Bad Tasks (Too Large - Split These)
- "Implement entire agent system" (split into:感知层, 决策层, 执行层, etc.)
- "Add all middleware" (split into one per middleware)

## Implementation Pattern

```python
# Ralph Loop Core (pseudo-code)
def ralph_loop(prd_path: str, max_iterations: int = 10):
    progress_file = "progress.txt"
    iteration = 0

    while iteration < max_iterations:
        # 1. Load tasks
        tasks = load_json(prd_path)

        # 2. Find next pending task (lowest ID first)
        task = find_next_pending(tasks)

        if not task:
            print("All tasks complete!")
            return

        # 3. Build context with learnings
        context = build_context(task, progress_file)

        # 4. Execute with AI
        result = execute_with_llm(context)

        # 5. Verify
        if verify(task["verification"]):
            # 6. Update status
            update_task_status(prd_path, task["id"], "done")
            append_learnings(progress_file, task, "Success")
        else:
            # 7. Record failure, will retry
            append_learnings(progress_file, task, f"Failed: {result['error']}")

        iteration += 1
```

## Usage in This Project

For implementing `Ralph智能体改造方案.md`:

1. **Parse the design doc** into atomic tasks
2. **Create prd.json** with each module as a task
3. **Execute Ralph loop** - each iteration implements one module
4. **Verify** - run typecheck, basic import tests
5. **Learn** - record what worked and what didn't

### Task Breakdown Example

From `Ralph智能体改造方案.md`:

| Phase | Task | Verification |
|-------|------|-------------|
| Phase 1 | Create `infrastructure/task_state.py` | `python -c "from infrastructure.task_state import TaskState; print('OK')"` |
| Phase 1 | Create `infrastructure/tool_verifier.py` | `python -c "from infrastructure.tool_verifier import ToolVerifier; print('OK')"` |
| Phase 2 | Create `middleware/decision_small.py` | Import + basic instantiation |
| Phase 2 | Create `middleware/execution_small.py` | Import + basic instantiation |
| Phase 3 | Create `agent/ralph_loop.py` | Import + basic instantiation |
| Phase 4 | Integrate with LangGraph | Run graph compilation test |
| Phase 5 | End-to-end test | Execute full loop with test task |

## Starting the Loop

To start implementing the Ralph改造方案:

1. Say "start Ralph loop" or "run ralph"
2. I'll parse the design doc into tasks
3. Create `prd.json` with all implementation tasks
4. Execute loop: each iteration implements one module
5. Continue until all phases complete

## Important Notes

- Ralph is designed for **small, verifiable tasks** - not large features
- Each iteration should complete in one AI call
- If a task fails 3 times, record it and move on (manual intervention needed)
- Always verify with concrete commands, not "looks good"
