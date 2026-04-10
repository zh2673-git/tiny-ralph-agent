"""
Agent 状态定义

用于 LangGraph StateGraph 的状态类型
"""

from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph.message import add_messages
from langgraph.channels.last_value import LastValue
from operator import add


class AgentState(TypedDict):
    """
    Agent 状态定义

    中间件链完整状态：
    - perception → decision → execute → feedback → (循环)
    """
    messages: Annotated[list, add_messages]

    goal: str

    perception_result: Dict[str, Any]

    sub_goals: List[str]

    plan: List[Dict[str, Any]]

    next_action: str

    current_step: Annotated[int, LastValue]

    execution_result: Dict[str, Any]

    execution_results: List[Dict[str, Any]]

    evaluation: Dict[str, Any]

    deviation: Dict[str, Any]

    error: str

    iteration: int
