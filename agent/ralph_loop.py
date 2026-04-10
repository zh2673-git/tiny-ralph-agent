"""
Ralph 循环核心

Ralph 风格自主循环：
- 每次迭代都是全新的上下文
- 状态通过文件持久化
- 极度结构化的 Prompt
- 小模型友好的指令
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from infrastructure.task_state import TaskState
from infrastructure.tool_verifier import ToolVerifier
from middleware.decision import DecisionMiddleware
from middleware.execution import ExecutionMiddleware
from middleware.feedback import FeedbackMiddleware


class RalphLoop:
    """
    Ralph 循环核心

    工作流程：
    1. 创建任务 (create_task)
    2. 生成执行计划 (plan)
    3. 循环执行直到完成:
       a. 构建全新上下文 (build_fresh_context)
       b. 调用小模型 (call_small_model)
       c. 处理响应 (process_response)
       d. 更新状态 (update_state)
       e. 反馈判断 (feedback)
    4. 记录学习 (record_learnings)
    """

    def __init__(
        self,
        llm = None,
        state_dir: str = "./runtime",
        tools_dir: str = "./tools/custom",
        max_iterations: int = 10
    ):
        self.task_state = TaskState(state_dir)
        self.tool_verifier = ToolVerifier(tools_dir)
        self.decision = DecisionMiddleware(llm)
        self.execution = ExecutionMiddleware(
            self.tool_verifier,
            tools_dir,
            max_retries=3
        )
        self.feedback = FeedbackMiddleware()
        self.llm = llm
        self.max_iterations = max_iterations

    def run(self, task_id: str) -> Dict[str, Any]:
        """
        运行 Ralph 循环

        主循环：
        - 加载状态
        - 生成计划（如果需要）
        - 执行当前步骤
        - 评估反馈
        - 重复直到完成或失败
        """
        state = self.task_state.load_task(task_id)
        if not state:
            return {"error": f"Task {task_id} not found"}

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n=== Ralph Iteration {iteration} ===")

            context = self._build_fresh_context(state)

            response = self._call_small_model(context)

            result = self._process_response(state, response)

            state = self._update_state(state, result)

            evaluation = self.feedback.evaluate(state)

            print(f"Evaluation: {evaluation['reason']}")
            print(f"Next action: {evaluation['next_action']}")
            print(f"Learnings so far: {len(evaluation['learnings'])}")

            if evaluation["next_action"] == "complete":
                self._record_learnings(task_id, evaluation["learnings"])
                self.task_state.complete_task(task_id, {
                    "iterations": iteration,
                    "learnings": evaluation["learnings"]
                })
                return {
                    "success": True,
                    "task_id": task_id,
                    "iterations": iteration,
                    "learnings": evaluation["learnings"]
                }

            elif evaluation["next_action"] == "fail":
                self._record_learnings(task_id, evaluation["learnings"])
                self.task_state.fail_task(task_id, evaluation["reason"])
                return {
                    "success": False,
                    "task_id": task_id,
                    "reason": evaluation["reason"],
                    "learnings": evaluation["learnings"]
                }

        return {
            "success": False,
            "task_id": task_id,
            "reason": "达到最大迭代次数",
            "iterations": iteration
        }

    def _build_fresh_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建全新的上下文

        Ralph 核心：每次迭代都是全新的开始
        只传递必要的状态信息，不依赖模型记忆
        """
        atomic_plan = state.get("atomic_plan", [])
        current_step_index = state.get("current_step", 0)

        current_step = None
        if current_step_index < len(atomic_plan):
            current_step = atomic_plan[current_step_index]

        available_tools = list(self.tool_verifier.list_tools())

        context = {
            "task_id": state.get("task_id"),
            "goal": state.get("goal"),
            "current_step": current_step,
            "current_step_index": current_step_index,
            "total_steps": len(atomic_plan),
            "available_tools": available_tools,
            "tool_inventory": state.get("tool_inventory", {}),
            "learnings": state.get("learnings", []),
            "execution_log": state.get("execution_log", [])[-5:],
            "timestamp": datetime.now().isoformat()
        }

        return context

    def _build_step_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建极度结构化的 Prompt

        小模型友好的指令格式
        """
        current_step = context.get("current_step")
        step_info = ""

        if current_step:
            step_info = f"""
当前步骤: {current_step.get('description', 'N/A')}
步骤ID: {current_step.get('step_id', 'N/A')}
需要工具: {current_step.get('required_tool', 'N/A')}
工具状态: {current_step.get('tool_status', 'N/A')}
预期输出: {current_step.get('expected_output', 'N/A')}
验证方法: {current_step.get('verification_method', 'N/A')}
"""
        else:
            step_info = "所有计划步骤已完成，等待最终验证。"

        prompt = f"""你是 Ralph，一个自主执行任务的 AI 助手。

任务目标: {context.get('goal', 'N/A')}

步骤进度: {context.get('current_step_index', 0)} / {context.get('total_steps', 0)}

{step_info}

已创建的工具:
{json.dumps(context.get('tool_inventory', {}), ensure_ascii=False, indent=2)}

最近执行记录:
{json.dumps(context.get('execution_log', []), ensure_ascii=False, indent=2)}

学习记录:
{chr(10).join(f"- {l}" for l in context.get('learnings', []))}

请根据以上信息执行当前步骤。

如果需要创建工具，返回:
{{
  "action": "create_tool",
  "tool_name": "工具名",
  "tool_code": "Python代码"
}}

如果执行工具，返回:
{{
  "action": "execute",
  "tool_name": "工具名",
  "params": {{}}
}}

如果步骤完成，返回:
{{
  "action": "step_complete",
  "result": "执行结果描述"
}}

如果遇到错误，返回:
{{
  "action": "error",
  "error": "错误描述"
}}
"""
        return prompt

    def _call_small_model(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用小模型

        如果没有配置 LLM，返回模拟响应
        """
        if self.llm is None:
            return self._mock_llm_response(context)

        prompt = self._build_step_prompt(context)

        try:
            if hasattr(self.llm, 'chat'):
                from langchain_core.messages import HumanMessage
                response = self.llm.chat(messages=[HumanMessage(content=prompt)])
                response_text = response.generations[0].message.content
            else:
                response_text = self.llm.invoke(prompt)

            return self._parse_response(response_text)
        except Exception as e:
            return {
                "action": "error",
                "error": f"LLM 调用失败: {str(e)}"
            }

    def _mock_llm_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """模拟 LLM 响应（用于测试）"""
        current_step = context.get("current_step")

        if not current_step:
            return {
                "action": "step_complete",
                "result": "所有步骤已完成"
            }

        tool_status = current_step.get("tool_status", "available")

        if tool_status == "need_create":
            return {
                "action": "create_tool",
                "tool_name": current_step.get("required_tool"),
                "tool_code": f'''
def execute(**params) -> dict:
    """Auto-created tool: {current_step.get("required_tool")}"""
    return {{"result": "tool executed"}}
'''
            }

        return {
            "action": "execute",
            "tool_name": current_step.get("required_tool"),
            "params": {}
        }

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """解析 LLM 响应"""
        if isinstance(response, dict):
            return response

        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {
                    "action": "error",
                    "error": f"无法解析响应: {response[:100]}"
                }

        return {
            "action": "error",
            "error": f"未知响应类型: {type(response)}"
        }

    def _process_response(
        self,
        state: Dict[str, Any],
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理响应

        根据 action 执行相应操作
        """
        action = response.get("action")

        if action == "create_tool":
            tool_name = response.get("tool_name")
            tool_code = response.get("tool_code")

            verify_result = self.tool_verifier.verify(tool_name, tool_code)

            if verify_result["pass"]:
                self.tool_verifier.register_tool(tool_name, {
                    "path": verify_result["tool_path"],
                    "description": f"Auto-created: {tool_name}",
                    "status": "available"
                })

                self.task_state.add_log(state["task_id"], {
                    "type": "tool_created",
                    "tool_name": tool_name,
                    "path": verify_result["tool_path"]
                })

                return {
                    "success": True,
                    "action": "tool_created",
                    "tool_name": tool_name
                }
            else:
                return {
                    "success": False,
                    "action": "tool_creation_failed",
                    "error": verify_result["reason"]
                }

        elif action == "execute":
            tool_name = response.get("tool_name")
            params = response.get("params", {})

            step = state.get("atomic_plan", [])[state.get("current_step", 0)]
            step["status"] = "in_progress"

            result = self.execution.execute_step(step, state)

            self.task_state.add_log(state["task_id"], {
                "type": "execution",
                "tool": tool_name,
                "result": result
            })

            if result.get("success"):
                return {
                    "success": True,
                    "action": "executed",
                    "result": result
                }
            else:
                return {
                    "success": False,
                    "action": "execution_failed",
                    "error": result.get("error")
                }

        elif action == "step_complete":
            current_step_index = state.get("current_step", 0)

            if current_step_index < len(state.get("atomic_plan", [])):
                state["atomic_plan"][current_step_index]["status"] = "completed"

            state["current_step"] = current_step_index + 1
            state["retry_count"] = 0

            return {
                "success": True,
                "action": "step_completed",
                "completed_step": current_step_index
            }

        elif action == "error":
            state["retry_count"] = state.get("retry_count", 0) + 1

            self.task_state.add_log(state["task_id"], {
                "type": "error",
                "message": response.get("error")
            })

            return {
                "success": False,
                "action": "error",
                "error": response.get("error")
            }

        return {
            "success": False,
            "action": "unknown_action",
            "error": f"未知 action: {action}"
        }

    def _update_state(
        self,
        state: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新状态"""
        task_id = state.get("task_id")

        if result.get("success"):
            if result.get("action") == "step_completed":
                completed_step = result.get("completed_step", 0)
                self.task_state.update_step(
                    task_id,
                    completed_step,
                    {"status": "completed"}
                )
                self.task_state.advance_step(task_id)
            elif result.get("action") == "tool_created":
                tool_name = result.get("tool_name")
                self.task_state.mark_tool_created(task_id, tool_name, f"./tools/custom/{tool_name}.py")
        else:
            error = result.get("error", "Unknown error")
            self.task_state.set_retry(task_id, error)

        return self.task_state.load_task(task_id)

    def _record_learnings(self, task_id: str, learnings: List[str]):
        """记录学习"""
        for learning in learnings:
            self.task_state.append_learnings(task_id, learning)

    def create_and_run(self, goal: str) -> Dict[str, Any]:
        """创建任务并运行"""
        task_id = self.task_state.create_task(goal)

        available_tools = self.tool_verifier.discover_tools()

        plan = self.decision.generate_execution_plan(
            goal,
            available_tools
        )

        self.task_state.set_atomic_plan(task_id, plan["atomic_plan"])

        return self.run(task_id)
