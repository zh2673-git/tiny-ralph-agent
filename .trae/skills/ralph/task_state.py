"""Task state management for Ralph loop."""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    """Represents a single task in the PRD."""
    id: int
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    verification: str = ""
    retry_count: int = 0
    max_retries: int = 3
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary."""
        data = data.copy()
        data['status'] = TaskStatus(data.get('status', 'pending'))
        return cls(**data)

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries

    def mark_failed(self, error: str):
        """Mark task as failed with error message."""
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.retry_count += 1

    def mark_done(self):
        """Mark task as completed."""
        self.status = TaskStatus.DONE
        self.error_message = ""

    def mark_in_progress(self):
        """Mark task as in progress."""
        self.status = TaskStatus.IN_PROGRESS


@dataclass
class ProjectState:
    """Represents the entire project state from PRD."""
    project: str
    tasks: List[Task] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert project state to dictionary."""
        return {
            'project': self.project,
            'tasks': [t.to_dict() for t in self.tasks],
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectState':
        """Create project state from dictionary."""
        tasks = [Task.from_dict(t) for t in data.get('tasks', [])]
        return cls(
            project=data.get('project', 'Unknown'),
            tasks=tasks,
            metadata=data.get('metadata', {})
        )


class TaskStateManager:
    """Manages task state persistence and operations."""

    def __init__(self, prd_path: str):
        self.prd_path = Path(prd_path)
        self.state: Optional[ProjectState] = None

    def load(self) -> ProjectState:
        """Load project state from PRD file."""
        if not self.prd_path.exists():
            raise FileNotFoundError(f"PRD file not found: {self.prd_path}")

        with open(self.prd_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.state = ProjectState.from_dict(data)
        return self.state

    def save(self):
        """Save project state to PRD file."""
        if self.state is None:
            raise RuntimeError("No state loaded")

        with open(self.prd_path, 'w', encoding='utf-8') as f:
            json.dump(self.state.to_dict(), f, indent=2, ensure_ascii=False)

    def get_next_pending_task(self) -> Optional[Task]:
        """Get the next pending task with lowest ID."""
        if self.state is None:
            self.load()

        pending_tasks = [
            t for t in self.state.tasks
            if t.status == TaskStatus.PENDING
            or (t.status == TaskStatus.FAILED and t.can_retry())
        ]

        if not pending_tasks:
            return None

        return min(pending_tasks, key=lambda t: t.id)

    def update_task(self, task: Task):
        """Update a task in the state."""
        if self.state is None:
            raise RuntimeError("No state loaded")

        for i, t in enumerate(self.state.tasks):
            if t.id == task.id:
                self.state.tasks[i] = task
                break

        self.save()

    def get_progress(self) -> Dict[str, int]:
        """Get progress statistics."""
        if self.state is None:
            self.load()

        total = len(self.state.tasks)
        by_status = {}
        for task in self.state.tasks:
            status = task.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            'total': total,
            'completed': by_status.get('done', 0),
            'pending': by_status.get('pending', 0),
            'failed': by_status.get('failed', 0),
            'in_progress': by_status.get('in_progress', 0)
        }

    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        if self.state is None:
            self.load()

        return all(
            t.status == TaskStatus.DONE
            for t in self.state.tasks
        )

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        if self.state is None:
            self.load()
        return self.state.tasks

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """Get task by ID."""
        if self.state is None:
            self.load()

        for task in self.state.tasks:
            if task.id == task_id:
                return task
        return None
