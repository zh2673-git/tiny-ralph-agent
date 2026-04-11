"""
执行中间件 - 小模型优化版

Ralph 风格：
- 工具自造循环 - 小模型可以造工具
- 单步执行 - 每步只做一个操作
- 验证通过才下一步
- max_retries 防止无限循环
"""

import importlib.util
from typing import Dict, Any, Optional, Callable
from pathlib import Path


class ExecutionMiddleware:
    """
    执行中间件 - 小模型版

    核心职责：
    1. 工具创建循环
    2. 单步执行
    3. 结果验证
    4. 错误处理和重试
    """

    def __init__(
        self,
        tool_verifier,
        tool_dir: str = "./tools/custom",
        max_retries: int = 3
    ):
        self.tool_verifier = tool_verifier
        self.tool_dir = Path(tool_dir)
        self.max_retries = max_retries

    def execute_step(
        self,
        step: Dict[str, Any],
        state: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行单个步骤

        流程：
        1. 检查工具状态
        2. 如果需要创建工具 -> 造工具
        3. 执行工具
        4. 验证结果
        """
        required_tool = step.get("required_tool")
        tool_status = step.get("tool_status", "available")

        if tool_status == "need_create":
            return self._handle_tool_creation(step, state)
        else:
            return self._handle_normal_execution(step, state)

    def _handle_tool_creation(
        self,
        step: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理工具创建 - 需要由模型生成工具代码"""
        required_tool = step.get("required_tool")

        return {
            "success": False,
            "error": f"工具 '{required_tool}' 不存在，请创建它",
            "action": "tool_not_found",
            "tool_name": required_tool,
            "hint": "使用 create_tool action 创建新工具"
        }

    def _handle_normal_execution(
        self,
        step: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理普通执行"""
        required_tool = step.get("required_tool")
        tool_path = self.tool_dir / f"{required_tool}.py"

        if not tool_path.exists():
            return {
                "success": False,
                "error": f"工具 {required_tool} 文件不存在",
                "action": "create_tool"
            }

        try:
            result = self._run_tool(required_tool, tool_path, state, params)
            return self._verify_result(step, result)
        except Exception as e:
            return {
                "success": False,
                "error": f"执行错误: {str(e)}",
                "action": "retry"
            }

    def _generate_tool_code(
        self,
        tool_name: str,
        purpose: str,
        state: Dict[str, Any]
    ) -> str:
        """
        生成工具代码

        小模型友好的模板
        """
        template = f'''
"""
工具: {tool_name}
目的: {purpose}
自动生成 by Ralph
"""

def execute(**params) -> dict:
    """
    执行 {tool_name}

    返回格式:
        {{"result": ..., "error": ...}}
    """
    try:
        # 获取上下文信息
        task_goal = params.get("task_goal", "")
        current_step = params.get("current_step", 0)

        # 实现工具逻辑
        # TODO: 根据 purpose 实现具体功能

        result = {{"message": "{tool_name} executed", "step": current_step}}

        return {{"result": result}}

    except Exception as e:
        return {{"error": str(e)}}
'''
        return template

    def _run_tool(
        self,
        tool_name: str,
        tool_path: Path,
        state: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行工具"""
        spec = importlib.util.spec_from_file_location(tool_name, tool_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载工具 {tool_name}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, 'execute'):
            raise AttributeError(f"工具 {tool_name} 缺少 execute 函数")

        exec_params = {
            "task_goal": state.get("goal", ""),
            "current_step": state.get("current_step", 0),
            "state": state,
            **params
        }

        result = module.execute(**exec_params)

        if not isinstance(result, dict):
            raise TypeError(f"工具返回格式错误: {type(result)}")

        return result

    def _verify_result(
        self,
        step: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证执行结果"""
        if "error" in result:
            return {
                "success": False,
                "error": result["error"],
                "action": "retry"
            }

        expected_output = step.get("expected_output", "")

        return {
            "success": True,
            "result": result.get("result"),
            "expected": expected_output,
            "action": "continue"
        }

    def get_tool_status(
        self,
        tool_name: str,
        tool_inventory: Dict[str, Any]
    ) -> str:
        """获取工具状态"""
        if tool_name in tool_inventory:
            return tool_inventory[tool_name].get("status", "unknown")
        return "not_found"

    def should_retry(
        self,
        result: Dict[str, Any],
        retry_count: int
    ) -> bool:
        """判断是否应该重试"""
        if not result.get("success"):
            if retry_count < self.max_retries:
                return True
        return False
