"""Ralph - Autonomous AI Agent Loop for iterative task completion."""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass, field

from task_state import TaskStateManager, Task, TaskStatus
from tool_verifier import ToolVerifier, VerificationResult


@dataclass
class Learning:
    """Represents a learning from an iteration."""
    iteration: int
    task_id: int
    task_title: str
    success: bool
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_text(self) -> str:
        """Convert learning to text format for progress file."""
        status = "Success" if self.success else "Failed"
        return f"""=== Iteration {self.iteration} ===
Task [{self.task_id}]: {self.task_title}
Status: {status}
Message: {self.message}
Timestamp: {self.timestamp}

"""


class ProgressTracker:
    """Tracks progress and learnings across iterations."""

    def __init__(self, progress_path: str):
        self.progress_path = Path(progress_path)
        self.learnings: List[Learning] = []

    def add_learning(self, learning: Learning):
        """Add a learning entry."""
        self.learnings.append(learning)
        self._append_to_file(learning)

    def _append_to_file(self, learning: Learning):
        """Append learning to progress file."""
        with open(self.progress_path, 'a', encoding='utf-8') as f:
            f.write(learning.to_text())

    def get_learnings_text(self) -> str:
        """Get all learnings as text."""
        if self.progress_path.exists():
            return self.progress_path.read_text(encoding='utf-8')
        return ""

    def get_recent_learnings(self, count: int = 5) -> List[Learning]:
        """Get recent learnings."""
        return self.learnings[-count:] if self.learnings else []

    def clear(self):
        """Clear progress file."""
        if self.progress_path.exists():
            self.progress_path.unlink()
        self.learnings = []


class RalphLoop:
    """
    Ralph - Autonomous AI Agent Loop for iterative task completion.

    Core principles:
    1. Fresh Context Each Iteration - Each loop starts with clean context
    2. Small Tasks - Each task should complete in one context window
    3. Explicit Memory - State persists via files, not model context
    4. Verification - Quality checks gate completion
    5. Learnings - Record patterns/gotchas for future iterations
    """

    def __init__(
        self,
        prd_path: str,
        progress_path: Optional[str] = None,
        max_iterations: int = 50,
        verifier: Optional[ToolVerifier] = None
    ):
        """
        Initialize Ralph Loop.

        Args:
            prd_path: Path to prd.json file
            progress_path: Path to progress.txt file (default: progress.txt in same dir)
            max_iterations: Maximum number of iterations
            verifier: ToolVerifier instance (default: new instance)
        """
        self.prd_path = Path(prd_path)
        self.progress_path = Path(progress_path) if progress_path else self.prd_path.parent / 'progress.txt'
        self.max_iterations = max_iterations

        self.task_manager = TaskStateManager(str(self.prd_path))
        self.progress_tracker = ProgressTracker(str(self.progress_path))
        self.verifier = verifier or ToolVerifier()

        self.iteration = 0
        self._task_handler: Optional[Callable[[Task, str], tuple[bool, str]]] = None

    def set_task_handler(self, handler: Callable[[Task, str], tuple[bool, str]]):
        """
        Set the task handler function.

        Args:
            handler: Function that takes (task, context) and returns (success, message)
        """
        self._task_handler = handler

    def build_context(self, task: Task) -> str:
        """
        Build context for task execution including learnings.

        Args:
            task: Current task

        Returns:
            Context string
        """
        learnings_text = self.progress_tracker.get_learnings_text()

        context_parts = [
            f"=== Task {task.id}: {task.title} ===",
            f"Description: {task.description}",
            f"Verification: {task.verification}",
        ]

        if task.retry_count > 0:
            context_parts.append(f"Retry attempt: {task.retry_count + 1}/{task.max_retries}")

        if task.error_message:
            context_parts.append(f"Previous error: {task.error_message}")

        if learnings_text:
            context_parts.extend([
                "",
                "=== Previous Learnings ===",
                learnings_text
            ])

        return "\n".join(context_parts)

    def run_single_iteration(self) -> bool:
        """
        Run a single iteration of the Ralph loop.

        Returns:
            True if there are more tasks, False if complete
        """
        if self.iteration >= self.max_iterations:
            print(f"Reached max iterations ({self.max_iterations})")
            return False

        self.iteration += 1
        print(f"\n=== Iteration {self.iteration} ===")

        # 1. Find next pending task
        task = self.task_manager.get_next_pending_task()

        if task is None:
            print("All tasks complete!")
            return False

        print(f"Processing task {task.id}: {task.title}")
        task.mark_in_progress()
        self.task_manager.update_task(task)

        # 2. Build context
        context = self.build_context(task)

        # 3. Execute task (using handler)
        if self._task_handler is None:
            raise RuntimeError("No task handler set. Call set_task_handler() first.")

        try:
            success, message = self._task_handler(task, context)
        except Exception as e:
            success = False
            message = f"Task handler error: {str(e)}"

        # 4. Verify
        if success and task.verification:
            print(f"Running verification: {task.verification}")
            verify_result = self.verifier.verify(task.verification)

            if verify_result.result == VerificationResult.SUCCESS:
                print(f"✓ Verification passed ({verify_result.duration_ms:.0f}ms)")
                success = True
            else:
                print(f"✗ Verification failed: {verify_result.stderr or verify_result.stdout}")
                success = False
                message = f"Verification failed: {verify_result.stderr or verify_result.stdout}"

        # 5. Update state and record learning
        if success:
            task.mark_done()
            self.task_manager.update_task(task)
            print(f"✓ Task {task.id} completed")
        else:
            task.mark_failed(message)
            self.task_manager.update_task(task)
            print(f"✗ Task {task.id} failed: {message}")

        learning = Learning(
            iteration=self.iteration,
            task_id=task.id,
            task_title=task.title,
            success=success,
            message=message
        )
        self.progress_tracker.add_learning(learning)

        return True

    def run(self) -> Dict[str, Any]:
        """
        Run the Ralph loop until completion or max iterations.

        Returns:
            Summary dict with results
        """
        print(f"Starting Ralph Loop")
        print(f"PRD: {self.prd_path}")
        print(f"Progress: {self.progress_path}")

        # Load initial state
        self.task_manager.load()
        progress = self.task_manager.get_progress()
        print(f"Tasks: {progress['total']} total, {progress['pending']} pending, {progress['completed']} completed")

        # Run loop
        while self.run_single_iteration():
            pass

        # Final summary
        progress = self.task_manager.get_progress()
        summary = {
            'iterations': self.iteration,
            'total_tasks': progress['total'],
            'completed': progress['completed'],
            'failed': progress['failed'],
            'pending': progress['pending'],
            'complete': self.task_manager.is_complete()
        }

        print(f"\n=== Ralph Loop Complete ===")
        print(f"Iterations: {summary['iterations']}")
        print(f"Tasks: {summary['completed']}/{summary['total_tasks']} completed")
        print(f"Failed: {summary['failed']}")
        print(f"Pending: {summary['pending']}")

        return summary

    def reset(self):
        """Reset all tasks to pending state."""
        state = self.task_manager.load()
        for task in state.tasks:
            task.status = TaskStatus.PENDING
            task.retry_count = 0
            task.error_message = ""
        self.task_manager.save()
        self.progress_tracker.clear()
        self.iteration = 0
        print("Ralph loop reset")

    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        progress = self.task_manager.get_progress()
        return {
            'iteration': self.iteration,
            'progress': progress,
            'is_complete': self.task_manager.is_complete()
        }


def create_prd_template(project_name: str, tasks: List[Dict[str, Any]], output_path: str):
    """
    Create a PRD template file.

    Args:
        project_name: Name of the project
        tasks: List of task dicts with 'title', 'description', 'verification'
        output_path: Path to save prd.json
    """
    prd_data = {
        'project': project_name,
        'tasks': [
            {
                'id': i + 1,
                'title': t['title'],
                'description': t['description'],
                'status': 'pending',
                'verification': t.get('verification', ''),
                'retry_count': 0,
                'max_retries': 3
            }
            for i, t in enumerate(tasks)
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(prd_data, f, indent=2, ensure_ascii=False)

    print(f"Created PRD template: {output_path}")


# Example usage
if __name__ == '__main__':
    # Example task handler
    def example_handler(task: Task, context: str) -> tuple[bool, str]:
        """Example task handler - replace with actual implementation."""
        print(f"Executing: {task.title}")
        print(f"Context:\n{context}")
        # Here you would call the AI or perform the actual work
        return True, "Task completed successfully"

    # Example: Create and run Ralph loop
    # ralph = RalphLoop('prd.json')
    # ralph.set_task_handler(example_handler)
    # ralph.run()
    pass
