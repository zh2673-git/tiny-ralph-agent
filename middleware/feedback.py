"""
反馈中间件 - 执行评估
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger("middleware.feedback")


class FeedbackMiddleware:
    def __init__(self, llm=None, memory=None, context=None):
        self.llm = llm
        self.memory = memory
        self.context = context

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = state.get("execution_result", {})
        plan = state.get("plan", [])
        current_step = state.get("current_step", 0)
        execution_results = state.get("execution_results", [])

        evaluation = self._evaluate(execution_result)
        deviation = self._compare(plan, current_step)
        next_action = self._decide_next_step(current_step, len(plan), evaluation)

        status = evaluation.get("status", "unknown")
        rate = deviation.get("completion_rate", 0)
        print(f"📊 反馈 → 评估: {status} | 完成: {rate*100:.0f}% | 下一步: {next_action}")

        return {
            "evaluation": evaluation,
            "deviation": deviation,
            "next_action": next_action
        }

    def _evaluate(self, result: Dict) -> Dict:
        status = result.get("status", "unknown")
        if status == "completed":
            return {"status": "success"}
        elif status == "error":
            return {"status": "error"}
        return {"status": "partial"}

    def _compare(self, plan: List, current_step: int) -> Dict:
        total = len(plan)
        completed = sum(1 for p in plan if p.get("status") == "completed")
        return {
            "total_steps": total,
            "completed_steps": completed,
            "completion_rate": completed / total if total > 0 else 1.0
        }

    def _decide_next_step(self, current_step: int, plan_len: int, evaluation: Dict) -> str:
        status = evaluation.get("status", "unknown")
        if status == "partial" and current_step < plan_len:
            return "execute"
        if current_step >= plan_len:
            return "__end__"
        return "feedback"
