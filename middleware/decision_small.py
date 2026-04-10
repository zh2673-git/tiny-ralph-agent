"""
决策中间件 - 小模型优化版

Ralph 风格：
- 原子化任务拆解 - 每步只用一个工具
- 极度结构化 Prompt - 小模型能理解
- 工具绑定 - 每步明确需要什么工具
- 工具自造标记 - 需要造工具时明确标记
"""

from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass


@dataclass
class AtomicStep:
    """原子化步骤"""
    step_id: int
    description: str
    required_tool: str
    tool_status: str  # "available", "need_create", "creating"
    expected_output: str
    verification_method: str


class DecisionMiddleware:
    """
    决策中间件 - 小模型版

    核心职责：
    1. 拆解任务为原子化步骤
    2. 为每步绑定可用工具
    3. 标记需要创建的工具
    4. 生成极度结构化的执行计划
    """

    def __init__(self, llm=None, available_tools: List[str] = None):
        self.llm = llm
        self.available_tools = available_tools or []

    def decompose_to_atomic_steps(
        self,
        task: str,
        context: Optional[Dict] = None
    ) -> List[AtomicStep]:
        """
        拆解任务为原子化步骤

        原则：
        - 每个步骤只使用一个工具
        - 步骤描述简洁明确
        - 包含预期输出和验证方法
        """
        steps = []

        step_1 = AtomicStep(
            step_id=1,
            description=f"理解任务目标：{task}",
            required_tool="understand",
            tool_status="available",
            expected_output="明确任务目标和成功标准",
            verification_method="能复述任务目标"
        )
        steps.append(step_1)

        step_2 = AtomicStep(
            step_id=2,
            description="分析当前环境和可用资源",
            required_tool="analyze_context",
            tool_status="available",
            expected_output="列出当前状态和可用工具",
            verification_method="列出资源清单"
        )
        steps.append(step_2)

        step_3 = AtomicStep(
            step_id=3,
            description="确定第一步执行计划",
            required_tool="plan",
            tool_status="available",
            expected_output="具体的首个执行步骤",
            verification_method="步骤清晰可执行"
        )
        steps.append(step_3)

        return steps

    def bind_tools(
        self,
        steps: List[AtomicStep],
        available_tools: List[str]
    ) -> List[AtomicStep]:
        """
        为每个步骤绑定工具

        检查：
        - 工具是否已存在
        - 是否需要创建
        """
        for step in steps:
            if step.required_tool in available_tools:
                step.tool_status = "available"
            elif step.required_tool in ["understand", "analyze_context", "plan"]:
                step.tool_status = "available"
            else:
                step.tool_status = "need_create"
        return steps

    def check_and_mark_tool_creation(
        self,
        steps: List[AtomicStep]
    ) -> tuple[List[AtomicStep], List[str]]:
        """
        检查工具状态，标记需要创建的

        Returns:
            (updated_steps, tools_to_create)
        """
        tools_to_create = []

        for step in steps:
            if step.tool_status == "need_create":
                if step.required_tool not in tools_to_create:
                    tools_to_create.append(step.required_tool)

        return steps, tools_to_create

    def generate_execution_plan(
        self,
        task: str,
        available_tools: List[str],
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成完整的执行计划

        Returns:
            {
                "atomic_plan": [AtomicStep, ...],
                "tools_needed": [str, ...],
                "tools_to_create": [str, ...],
                "first_action": str,
                "plan_summary": str
            }
        """
        steps = self.decompose_to_atomic_steps(task, context)
        steps = self.bind_tools(steps, available_tools)
        steps, tools_to_create = self.check_and_mark_tool_creation(steps)

        plan = {
            "atomic_plan": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "required_tool": s.required_tool,
                    "tool_status": s.tool_status,
                    "expected_output": s.expected_output,
                    "verification_method": s.verification_method
                }
                for s in steps
            ],
            "tools_needed": list(set(s.required_tool for s in steps)),
            "tools_to_create": tools_to_create,
            "first_action": "create_tool" if tools_to_create else steps[0].required_tool,
            "plan_summary": f"共 {len(steps)} 个步骤，{len(tools_to_create)} 个工具需要创建"
        }

        return plan

    def create_tool_definition(
        self,
        tool_name: str,
        purpose: str,
        expected_params: Dict
    ) -> str:
        """
        生成工具代码模板

        小模型可以基于这个模板生成具体工具
        """
        template = f'''
def execute(**params) -> dict:
    """
    {purpose}

    参数:
        {', '.join(f'{k}: {v}' for k, v in expected_params.items())}

    返回:
        dict: {{"result": ..., "error": ...}}
    """
    try:
        # TODO: 实现工具逻辑
        pass
    except Exception as e:
        return {{"error": str(e)}}

    return {{"result": None}}
'''
        return template

    def should_create_tool(
        self,
        tool_name: str,
        tool_inventory: Dict[str, Any]
    ) -> bool:
        """检查是否需要创建工具"""
        if tool_name in tool_inventory:
            return tool_inventory[tool_name].get("status") == "available"
        return True

    def get_next_ready_step(
        self,
        atomic_plan: List[Dict],
        tool_inventory: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        获取下一个可执行的步骤

        规则：
        1. 找到第一个未完成的步骤
        2. 检查其工具是否可用或已完成创建
        """
        for step in atomic_plan:
            if step.get("status") in ["pending", "ready"]:
                required_tool = step.get("required_tool")
                if required_tool in ["understand", "analyze_context", "plan"]:
                    return step
                if required_tool in tool_inventory:
                    if tool_inventory[required_tool].get("status") == "available":
                        return step
                elif step.get("tool_status") == "need_create":
                    if required_tool in tool_inventory:
                        if tool_inventory[required_tool].get("status") == "available":
                            return step
        return None
