"""
决策中间件 - 目标拆解和规划
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command
from typing import Literal, Dict, Any, List
import logging

logger = logging.getLogger("middleware.decision")


class DecisionMiddleware:
    def __init__(self, llm: BaseChatModel, context: Any = None, prompt_templates: Any = None):
        self.llm = llm
        self.context = context
        self.prompts = prompt_templates or {}

    def __call__(self, state: Dict[str, Any]) -> Command[Literal["execute", "feedback", "__end__"]]:
        goal = state.get("goal", "")
        perception_result = state.get("perception_result", {})
        current_step = state.get("current_step", 0)

        if not goal:
            return Command(update={"error": "No goal", "next_step": "__end__"}, goto="__end__")

        decision_context = self._build_context(state)
        sub_goals = self._decompose_goal(goal, decision_context)
        plan = self._generate_plan(sub_goals, decision_context)
        next_action = self._decide_next_action(plan, state)

        print(f"📋 决策 → 目标: {goal[:40]}{'...' if len(goal) > 40 else ''} | 计划: {len(plan)}步")

        return Command(
            update={"sub_goals": sub_goals, "plan": plan, "next_action": next_action},
            goto=next_action
        )

    def _build_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "perception_result": state.get("perception_result", {}),
            "messages": state.get("messages", []),
            "history_results": state.get("execution_results", []),
        }

    def _decompose_goal(self, goal: str, context: Dict[str, Any]) -> List[str]:
        if self.llm:
            try:
                system_prompt = """你是一个智能任务拆解助手。请将用户的目标拆解成子目标。

重要规则：
1. 如果用户问题是"你是谁"、"你是干什么的"、"介绍自己"等关于AI身份的问题，标记为[LIMITED]，不需要工具
2. 如果用户问题涉及实时信息（天气、新闻、股价、时间等），标记为[TOOL_NEEDED]，需要搜索工具
3. 如果用户问题仅需知识回答（解释概念、介绍事物等），标记为[LIMITED]
4. 如果用户问题需要多步操作，拆分为多个[TOOL_NEEDED]或[LIMITED]子目标

输出格式：
1. [TOOL_NEEDED/LIMITED] 子目标描述
2. [TOOL_NEEDED/LIMITED] 子目标描述

示例：
输入：你是谁，苏州天气怎么样
输出：
1. [LIMITED] 回答“你是谁”
2. [TOOL_NEEDED] 查询苏州天气

输入：解释量子计算是什么
输出：
1. [LIMITED] 解释量子计算的概念"""

                response = self.llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Goal: {goal}\n\nOutput:")
                ])
                content = response.content if hasattr(response, 'content') else str(response)

                sub_goals = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-')):
                        cleaned = line.lstrip('0123456789.-) ').strip()
                        if '[TOOL_NEEDED]' in cleaned or '[LIMITED]' in cleaned:
                            sub_goals.append(cleaned)

                if sub_goals:
                    return sub_goals

            except Exception as e:
                logger.warning(f"LLM 拆解失败: {e}")

        return [goal]

    def _generate_plan(self, sub_goals: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        plan = []
        for i, sg in enumerate(sub_goals):
            need_tool = "[TOOL_NEEDED]" in sg
            clean_goal = sg.replace("[TOOL_NEEDED]", "").replace("[LIMITED]", "").strip()
            plan.append({
                "step": i,
                "goal": clean_goal,
                "need_tool": need_tool,
                "status": "pending",
                "result": None
            })
        return plan

    def _decide_next_action(self, plan: List[Dict[str, Any]], state: Dict[str, Any]) -> Literal["execute", "feedback", "__end__"]:
        if not plan:
            return "__end__"
        current_step = state.get("current_step", 0)
        if current_step >= len(plan):
            return "feedback"
        return "execute"
