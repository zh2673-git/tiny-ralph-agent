"""
任务状态管理器 - Ralph 风格

核心原则：
- 状态持久化到 JSON 文件
- 每步执行后更新
- 支持中断恢复
- Append-only learnings
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


class TaskState:
    """
    任务状态管理器

    职责：
    1. 创建任务 - create_task(goal) -> task_id
    2. 加载任务 - load_task(task_id) -> state
    3. 更新步骤 - update_step(task_id, step_index, updates)
    4. 添加日志 - add_log(task_id, log_entry)
    5. 追加学习 - append_learnings(task_id, learning)
    6. 更新工具清单 - update_tool_inventory(task_id, tool_name, tool_info)
    7. 完成任务 - complete_task(task_id)
    """

    def __init__(self, state_dir: str = "./runtime"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, goal: str) -> str:
        """创建新任务，返回 task_id"""
        task_id = str(uuid.uuid4())[:8]

        state = {
            "task_id": task_id,
            "goal": goal,
            "created_at": self._now(),
            "updated_at": self._now(),
            "status": "in_progress",
            "atomic_plan": [],
            "tool_inventory": {},
            "current_step": 0,
            "retry_count": 0,
            "execution_log": [],
            "learnings": [],
            "used_skills": [],
            "created_skills": []
        }

        self._save_state(task_id, state)
        return task_id

    def load_task(self, task_id: str) -> Optional[Dict]:
        """加载任务状态"""
        state_file = self.state_dir / f"{task_id}.json"
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def update_step(self, task_id: str, step_index: int, updates: Dict):
        """更新某个步骤的状态"""
        state = self.load_task(task_id)
        if not state:
            return

        atomic_plan = state.get("atomic_plan", [])
        if step_index < len(atomic_plan):
            atomic_plan[step_index].update(updates)
            atomic_plan[step_index]["updated_at"] = self._now()

        state["atomic_plan"] = atomic_plan
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def set_atomic_plan(self, task_id: str, plan: list):
        """设置原子化计划"""
        state = self.load_task(task_id)
        if not state:
            return

        state["atomic_plan"] = plan
        state["current_step"] = 0
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def advance_step(self, task_id: str):
        """推进到下一步"""
        state = self.load_task(task_id)
        if not state:
            return

        state["current_step"] = state.get("current_step", 0) + 1
        state["retry_count"] = 0
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def set_retry(self, task_id: str, error: str):
        """设置重试状态"""
        state = self.load_task(task_id)
        if not state:
            return

        state["retry_count"] = state.get("retry_count", 0) + 1
        state["last_error"] = error
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def add_log(self, task_id: str, log_entry: Dict):
        """追加执行日志"""
        state = self.load_task(task_id)
        if not state:
            return

        if not isinstance(log_entry, dict):
            log_entry = {"message": str(log_entry)}

        log_entry["timestamp"] = self._now()
        state["execution_log"].append(log_entry)
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def append_learnings(self, task_id: str, learning: str):
        """追加学习记录（append-only）"""
        state = self.load_task(task_id)
        if not state:
            return

        state["learnings"].append(learning)
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def update_tool_inventory(
        self,
        task_id: str,
        tool_name: str,
        tool_info: Dict
    ):
        """更新工具清单"""
        state = self.load_task(task_id)
        if not state:
            return

        state["tool_inventory"][tool_name] = tool_info
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def mark_tool_created(
        self,
        task_id: str,
        tool_name: str,
        tool_path: str,
        verification_passed: bool = True
    ):
        """标记工具已创建"""
        self.update_tool_inventory(task_id, tool_name, {
            "status": "available" if verification_passed else "failed",
            "source": "custom",
            "path": tool_path,
            "created_at": self._now(),
            "verification": {"passed": verification_passed}
        })

    def add_used_skill(self, task_id: str, skill_name: str):
        """记录使用的技能"""
        state = self.load_task(task_id)
        if not state:
            return

        if "used_skills" not in state:
            state["used_skills"] = []
        if skill_name not in state["used_skills"]:
            state["used_skills"].append(skill_name)

        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def add_created_skill(self, task_id: str, skill_name: str):
        """记录创建的技能"""
        state = self.load_task(task_id)
        if not state:
            return

        if "created_skills" not in state:
            state["created_skills"] = []
        if skill_name not in state["created_skills"]:
            state["created_skills"].append(skill_name)

        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def complete_task(self, task_id: str, final_result: Dict = None):
        """标记任务完成"""
        state = self.load_task(task_id)
        if not state:
            return

        state["status"] = "completed"
        state["updated_at"] = self._now()
        if final_result:
            state["final_result"] = final_result

        self._save_state(task_id, state)

    def fail_task(self, task_id: str, reason: str):
        """标记任务失败"""
        state = self.load_task(task_id)
        if not state:
            return

        state["status"] = "failed"
        state["failure_reason"] = reason
        state["updated_at"] = self._now()
        self._save_state(task_id, state)

    def get_progress(self, task_id: str) -> Dict:
        """获取任务进度"""
        state = self.load_task(task_id)
        if not state:
            return {}

        atomic_plan = state.get("atomic_plan", [])
        total_steps = len(atomic_plan)
        completed_steps = sum(
            1 for step in atomic_plan
            if step.get("status") in ["completed", "done"]
        )

        return {
            "task_id": task_id,
            "goal": state.get("goal", ""),
            "status": state.get("status", "unknown"),
            "current_step": state.get("current_step", 0),
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "completion_rate": completed_steps / total_steps if total_steps > 0 else 0,
            "learnings_count": len(state.get("learnings", []))
        }

    def _save_state(self, task_id: str, state: Dict):
        """保存状态到文件"""
        state_file = self.state_dir / f"{task_id}.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _now(self) -> str:
        return datetime.now().isoformat()

    def list_tasks(self) -> list:
        """列出所有任务"""
        tasks = []
        for state_file in self.state_dir.glob("*.json"):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    tasks.append({
                        "task_id": state.get("task_id"),
                        "goal": state.get("goal", ""),
                        "status": state.get("status", "unknown"),
                        "created_at": state.get("created_at"),
                        "updated_at": state.get("updated_at")
                    })
            except Exception:
                pass
        return tasks
