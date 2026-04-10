"""
反馈中间件 - 小模型优化版

Ralph 风格：
- 规则判断 - 只有 pass/fail，无模糊结果
- 学习提取 - 从执行日志提取学习点
- 简单决策 - 下一步是什么
"""


from typing import Dict, Any, List, Literal


class FeedbackMiddleware:
    """
    反馈中间件 - 小模型版

    核心职责：
    1. 规则判断任务完成状态
    2. 提取学习点
    3. 决定下一步行动
    """

    def __init__(self):
        self.success_threshold = 0.8

    def evaluate(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估当前状态

        Returns:
            {
                "pass": bool,
                "reason": str,
                "learnings": [str, ...],
                "next_action": Literal["continue", "retry", "complete", "fail"]
            }
        """
        execution_log = state.get("execution_log", [])
        atomic_plan = state.get("atomic_plan", [])
        retry_count = state.get("retry_count", 0)

        all_completed = all(
            step.get("status") in ["completed", "done"]
            for step in atomic_plan
        )

        if all_completed:
            return {
                "pass": True,
                "reason": "所有步骤已完成",
                "learnings": self._extract_learnings(execution_log),
                "next_action": "complete"
            }

        failed_count = sum(
            1 for step in atomic_plan
            if step.get("status") == "failed"
        )

        if failed_count > 0:
            success_rate = (len(atomic_plan) - failed_count) / len(atomic_plan) if atomic_plan else 0
            if success_rate >= self.success_threshold:
                return {
                    "pass": True,
                    "reason": f"成功率 {success_rate:.0%}，已达阈值",
                    "learnings": self._extract_learnings(execution_log),
                    "next_action": "complete"
                }
            elif retry_count >= 3:
                return {
                    "pass": False,
                    "reason": f"失败 {failed_count} 次，已达最大重试次数",
                    "learnings": self._extract_learnings(execution_log),
                    "next_action": "fail"
                }

        current_step = state.get("current_step", 0)
        if current_step < len(atomic_plan):
            return {
                "pass": None,
                "reason": f"当前步骤 {current_step + 1}/{len(atomic_plan)}",
                "learnings": self._extract_learnings(execution_log),
                "next_action": "continue"
            }

        return {
            "pass": False,
            "reason": "未知状态",
            "learnings": [],
            "next_action": "fail"
        }

    def _extract_learnings(self, execution_log: List[Dict]) -> List[str]:
        """
        从执行日志提取学习点

        Ralph 风格：每条学习都是独立的、可操作的
        """
        learnings = []

        for entry in execution_log:
            if entry.get("type") == "error":
                error_msg = entry.get("message", "")
                if "import" in error_msg.lower():
                    learnings.append(f"Import错误: {error_msg}")
                elif "syntax" in error_msg.lower():
                    learnings.append(f"语法错误: {error_msg}")
                elif "timeout" in error_msg.lower():
                    learnings.append(f"超时问题: {error_msg}")
                else:
                    learnings.append(f"执行错误: {error_msg[:100]}")

            elif entry.get("type") == "success":
                msg = entry.get("message", "")
                learnings.append(f"成功: {msg[:80]}")

            elif entry.get("type") == "tool_created":
                tool_name = entry.get("tool_name", "")
                learnings.append(f"创建工具: {tool_name}")

        return learnings

    def decide_next_action(
        self,
        evaluation: Dict[str, Any],
        step_result: Dict[str, Any]
    ) -> Literal["continue", "retry", "end", "create_tool"]:
        """
        决定下一步行动

        规则：
        - step 成功 -> continue
        - tool 需要创建 -> create_tool
        - step 失败且可重试 -> retry
        - 任务完成 -> end
        - 任务失败 -> end
        """
        action = evaluation.get("next_action")
        step_action = step_result.get("action")

        if action == "complete":
            return "end"
        elif action == "fail":
            return "end"
        elif step_action == "create_tool":
            return "create_tool"
        elif step_action == "retry_step":
            return "continue"
        elif step_result.get("success"):
            return "continue"
        else:
            return "retry"

    def should_retry(self, retry_count: int, max_retries: int = 3) -> bool:
        """判断是否应该重试"""
        return retry_count < max_retries

    def is_task_complete(self, atomic_plan: List[Dict]) -> bool:
        """判断任务是否完成"""
        if not atomic_plan:
            return False
        return all(
            step.get("status") in ["completed", "done"]
            for step in atomic_plan
        )

    def get_completion_rate(self, atomic_plan: List[Dict]) -> float:
        """获取完成率"""
        if not atomic_plan:
            return 0.0
        completed = sum(
            1 for step in atomic_plan
            if step.get("status") in ["completed", "done"]
        )
        return completed / len(atomic_plan)
