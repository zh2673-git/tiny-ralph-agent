"""
使用 LangGraph 精细控制编排

中间件链：perception → decision → execute → feedback → (循环) → END
"""

from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState


def assemble_agent_with_langgraph(
    perception,
    decision,
    execution,
    feedback
):
    """
    中间件链流程：
    1. perception: 感知用户输入，设置 goal
    2. decision: 拆解目标，生成执行计划
    3. execute: 执行当前步骤
    4. feedback: 评估结果，决定下一步
       - 如果还有步骤 → 去 execute
       - 如果完成 → 结束
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("perception", perception)
    workflow.add_node("decision", decision)
    workflow.add_node("execute", execution)
    workflow.add_node("feedback", feedback)

    workflow.set_entry_point("perception")

    workflow.add_edge("perception", "decision")
    workflow.add_edge("decision", "execute")
    workflow.add_edge("execute", "feedback")

    workflow.add_conditional_edges(
        "feedback",
        lambda s: s.get("next_action", "__end__"),
        {
            "execute": "execute",
            "feedback": END,
            "__end__": END
        }
    )

    return workflow.compile(checkpointer=MemorySaver())


class RalphState(TypedDict):
    """Ralph 图状态"""
    task_id: str
    goal: str
    atomic_plan: list
    current_step: int
    tool_inventory: dict
    execution_log: list
    learnings: list
    next_action: Literal["continue", "retry", "end", "create_tool"]
    retry_count: int


def build_ralph_graph(
    ralph_loop,
    perception,
    decision,
    execution,
    feedback
):
    """
    Ralph 风格图结构

    流程：
    perception → decision → execute → feedback
         ↑                           ↓
         └───────────────────────────┘

    特点：
    - 小模型友好：每步只做一件事
    - 工具自造：需要时自动创建工具
    - 明确反馈：pass/fail，无模糊状态
    """
    workflow = StateGraph(RalphState)

    def perception_node(state: RalphState) -> RalphState:
        return state

    def decision_node(state: RalphState) -> RalphState:
        if not state.get("atomic_plan"):
            plan = decision.generate_execution_plan(
                state["goal"],
                list(ralph_loop.tool_verifier.list_tools())
            )
            state["atomic_plan"] = plan["atomic_plan"]
        return state

    def execute_node(state: RalphState) -> RalphState:
        step_index = state.get("current_step", 0)
        atomic_plan = state.get("atomic_plan", [])

        if step_index >= len(atomic_plan):
            state["next_action"] = "end"
            return state

        step = atomic_plan[step_index]
        result = execution.execute_step(step, state)

        if result.get("success"):
            state["execution_log"].append({
                "step": step_index,
                "result": result
            })
        else:
            state["retry_count"] = state.get("retry_count", 0) + 1
            state["execution_log"].append({
                "step": step_index,
                "error": result.get("error")
            })

        return state

    def feedback_node(state: RalphState) -> RalphState:
        evaluation = feedback.evaluate(state)
        state["next_action"] = evaluation["next_action"]

        if evaluation["learnings"]:
            state["learnings"].extend(evaluation["learnings"])

        if state["next_action"] == "continue":
            state["current_step"] = state.get("current_step", 0) + 1
            state["retry_count"] = 0

        return state

    workflow.add_node("perception", perception_node)
    workflow.add_node("decision", decision_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("feedback", feedback_node)

    workflow.set_entry_point("perception")

    workflow.add_edge("perception", "decision")
    workflow.add_edge("decision", "execute")
    workflow.add_edge("execute", "feedback")

    workflow.add_conditional_edges(
        "feedback",
        lambda s: s.get("next_action", "end"),
        {
            "continue": "execute",
            "retry": "execute",
            "create_tool": "execute",
            "end": END
        }
    )

    return workflow.compile(checkpointer=MemorySaver())
