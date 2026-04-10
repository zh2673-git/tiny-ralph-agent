"""
执行中间件 - 工具调用执行 + LLM 总结
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.types import Command
from typing import Literal, Dict, Any
import importlib


class ExecutionMiddleware:
    def __init__(self):
        self.llm = None
        self.tools = []
        self._load_tools()

    def _load_tools(self):
        """自动从 tools 包加载所有工具"""
        from tools import __all__ as tool_names
        for tool_name in tool_names:
            try:
                tool = getattr(importlib.import_module(f"tools.{tool_name}"), tool_name)
                self.tools.append(tool)
            except Exception:
                pass

    def set_llm(self, llm: BaseChatModel):
        self.llm = llm

    def add_tool(self, tool_func):
        self.tools.append(tool_func)

    def __call__(self, state: Dict[str, Any]) -> Command[Literal["feedback", "decision"]]:
        plan = state.get("plan", [])
        current_step = state.get("current_step", 0)
        goal = state.get("goal", "")

        if current_step >= len(plan):
            return Command(
                update={"execution_result": {"status": "completed", "message": "完成"}, "current_step": current_step},
                goto="feedback"
            )

        step = plan[current_step]
        step_goal = step.get("goal", goal)
        need_tool_from_decision = step.get("need_tool", True)

        need_tool = self._needs_tool(step_goal) if need_tool_from_decision else False
        if need_tool and self.tools:
            result = self._execute_with_tool(step_goal)
            tool_name = result.get("tool", "unknown")
        else:
            result = self._execute_with_llm(step_goal)
            tool_name = "llm_direct"

        updated_plan = plan.copy()
        updated_plan[current_step] = {**step, "status": "completed", "result": result}

        execution_results = state.get("execution_results", [])
        execution_results.append({"step": current_step, "goal": step_goal, "result": result})

        print(f"🔧 执行 → 步骤{current_step+1}: {step_goal[:40]}{'...' if len(step_goal) > 40 else ''} | 工具: {tool_name} | 状态: {result.get('status', 'unknown')}")

        summarized = self._summarize_result(result.get("result", ""), step_goal)

        ai_message = AIMessage(content=summarized)

        next_step = current_step + 1
        goto = "feedback"

        is_last_step = next_step >= len(updated_plan)
        exec_status = "completed" if is_last_step else result.get("status", "success")

        return Command(
            update={
                "plan": updated_plan,
                "current_step": next_step,
                "execution_result": {"status": exec_status, "tool": tool_name, "result": result.get("result", "")},
                "execution_results": execution_results,
                "messages": [ai_message]
            },
            goto=goto
        )

    def _needs_tool(self, goal: str) -> bool:
        """判断目标是否需要工具"""
        need_tool_keywords = ["搜索", "查找", "查询", "天气", "新闻", "最新", "实时", "当前"]
        no_tool_keywords = ["你好", "介绍", "解释", "什么是", "怎么做", "为什么", "帮我", "告诉我"]

        for kw in no_tool_keywords:
            if kw in goal and not any(nk in goal for nk in need_tool_keywords):
                return False

        for kw in need_tool_keywords:
            if kw in goal:
                return True

        return True

    def _execute_with_tool(self, goal: str) -> Dict[str, Any]:
        """使用工具执行"""
        for tool_func in self.tools:
            try:
                result = tool_func.invoke(goal)
                return {"status": "success", "tool": getattr(tool_func, 'name', 'unknown'), "result": result}
            except Exception:
                continue

        return {"status": "error", "tool": "none", "result": "所有工具执行失败"}

    def _execute_with_llm(self, goal: str) -> Dict[str, Any]:
        """直接使用 LLM 回答"""
        if not self.llm:
            return {"status": "success", "tool": "llm_direct", "result": f"无可用工具，使用 LLM: {goal}"}

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一个友好的智能助手，直接回答用户的问题。"),
                HumanMessage(content=goal)
            ])
            return {"status": "success", "tool": "llm_direct", "result": response.content if hasattr(response, 'content') else str(response)}
        except Exception:
            return {"status": "error", "tool": "llm_direct", "result": "LLM 执行失败"}

    def _summarize_result(self, raw_result: str, goal: str) -> str:
        if not raw_result:
            return "抱歉，我无法回答这个问题。"

        if len(raw_result) < 500:
            return raw_result

        if not self.llm:
            return raw_result

        prompt = f"""基于以下搜索结果，用简洁的语言总结回答用户的问题。

用户问题: {goal}

搜索结果:
{raw_result[:3000]}

请用简洁、友好的语言总结回答，控制在200字以内。"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一个智能助手，负责总结搜索结果并回答用户问题。"),
                HumanMessage(content=prompt)
            ])
            return response.content if hasattr(response, 'content') else str(response)
        except Exception:
            return raw_result
