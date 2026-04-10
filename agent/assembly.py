"""
使用 LangGraph / DeepAgents API 组装 Agent
"""

from typing import List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from middleware.perception import PerceptionMiddleware
from middleware.decision import DecisionMiddleware
from middleware.execution import ExecutionMiddleware
from middleware.feedback import FeedbackMiddleware
from infrastructure import SkillLoader


class AgentAssembly:
    """
    Agent 组装器 - 集成 SkillLoader
    """

    def __init__(
        self,
        skills_dir: str = "./skills",
        base_system_prompt: str = "你是一个智能助手。"
    ):
        self.skill_loader = SkillLoader(skills_dir)
        self.skill_loader.load_all_skills()
        self.base_system_prompt = base_system_prompt

    def list_available_skills(self) -> List[str]:
        """列出所有可用的 Skill"""
        return self.skill_loader.list_skills()


def assemble_agent_with_langgraph_main(
    llm: BaseChatModel,
    middleware_config: dict,
    skills_dir: str = "./skills"
):
    """
    使用 LangGraph 编排完整中间件链

    中间件链：perception → decision → execute → feedback → (循环)
    任务复杂度由决策模块自动判断
    """
    from agent.graph import assemble_agent_with_langgraph

    assembly = AgentAssembly(skills_dir=skills_dir)

    perception = PerceptionMiddleware(
        subscribed_sources=middleware_config.get("perception", {}).get("subscribed_sources", ["user_input"])
    )

    decision = DecisionMiddleware(
        llm=llm,
        context=None,
        prompt_templates={}
    )

    execution = ExecutionMiddleware()
    execution.set_llm(llm)

    feedback = FeedbackMiddleware(
        llm=llm,
        memory=None,
        context=None
    )

    agent = assemble_agent_with_langgraph(
        perception=perception,
        decision=decision,
        execution=execution,
        feedback=feedback
    )

    return agent, assembly
