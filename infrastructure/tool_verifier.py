"""
工具验证器 - Ralph 风格

核心职责：
1. 验证工具代码是否合格
2. 保存工具到指定目录
3. 提供工具发现功能
"""

import os
import importlib.util
import json
import ast
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ToolVerifier:
    """
    工具验证器

    验证流程：
    1. 检查文件存在
    2. 检查语法正确 (Python AST)
    3. 检查可导入
    4. 检查有 execute 函数
    5. 检查返回格式
    6. 执行测试验证
    """

    def __init__(self, tools_dir: str = "./tools/custom"):
        self.tools_dir = Path(tools_dir)
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.tools_dir / "registry.json"
        self._ensure_registry()

    def _ensure_registry(self):
        """确保注册表存在"""
        if not self.registry_file.exists():
            self._save_registry({})

    def _load_registry(self) -> Dict:
        with open(self.registry_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_registry(self, registry: Dict):
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)

    def verify(
        self,
        tool_name: str,
        code: str,
        test_input: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        验证工具代码

        Returns:
            {
                "pass": bool,
                "reason": str,
                "test_result": Optional[Dict],
                "tool_path": Optional[str]
            }
        """
        tool_path = self.tools_dir / f"{tool_name}.py"

        try:
            with open(tool_path, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            return {
                "pass": False,
                "reason": f"无法写入文件: {e}",
                "test_result": None,
                "tool_path": None
            }

        if not self._check_syntax(tool_path):
            return {
                "pass": False,
                "reason": "语法错误",
                "test_result": None,
                "tool_path": str(tool_path)
            }

        if not self._check_importable(tool_name, tool_path):
            return {
                "pass": False,
                "reason": "无法导入 - 缺少必要的导入或函数定义",
                "test_result": None,
                "tool_path": str(tool_path)
            }

        if not self._check_execute_function(tool_path):
            return {
                "pass": False,
                "reason": "缺少 execute 函数",
                "test_result": None,
                "tool_path": str(tool_path)
            }

        if not self._check_return_format(tool_name, tool_path):
            return {
                "pass": False,
                "reason": "execute 函数返回格式不正确 - 应返回包含 'result' 或 'error' 的字典",
                "test_result": None,
                "tool_path": str(tool_path)
            }

        if test_input:
            test_result = self._run_test(tool_name, test_input)
            if not test_result.get("success"):
                return {
                    "pass": False,
                    "reason": f"测试失败: {test_result.get('error', '未知错误')}",
                    "test_result": test_result,
                    "tool_path": str(tool_path)
                }
            return {
                "pass": True,
                "reason": "验证通过",
                "test_result": test_result,
                "tool_path": str(tool_path)
            }

        return {
            "pass": True,
            "reason": "验证通过（无测试数据）",
            "test_result": None,
            "tool_path": str(tool_path)
        }

    def _check_syntax(self, tool_path: Path) -> bool:
        """检查 Python 语法"""
        try:
            with open(tool_path, 'r', encoding='utf-8') as f:
                source = f.read()
            ast.parse(source)
            return True
        except SyntaxError as e:
            print(f"Syntax error: {e}")
            return False

    def _check_importable(self, tool_name: str, tool_path: Path) -> bool:
        """检查是否可导入"""
        try:
            spec = importlib.util.spec_from_file_location(tool_name, tool_path)
            if spec is None or spec.loader is None:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return True
        except Exception as e:
            print(f"Import error: {e}")
            return False

    def _check_execute_function(self, tool_path: Path) -> bool:
        """检查是否有 execute 函数"""
        try:
            with open(tool_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "execute":
                    return True
            return False
        except Exception:
            return False

    def _check_return_format(self, tool_name: str, tool_path: Path) -> bool:
        """检查 execute 函数返回格式"""
        try:
            spec = importlib.util.spec_from_file_location(tool_name, tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, 'execute'):
                return False

            import inspect
            sig = inspect.signature(module.execute)
            if len(sig.parameters) == 0:
                return True

            return True
        except Exception:
            return False

    def _run_test(self, tool_name: str, test_input: Dict) -> Dict:
        """运行测试"""
        try:
            spec = importlib.util.spec_from_file_location(
                tool_name,
                self.tools_dir / f"{tool_name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            result = module.execute(**test_input)

            if isinstance(result, dict) and ("result" in result or "error" in result):
                return {"success": True, "result": result}
            else:
                return {
                    "success": False,
                    "error": f"返回格式错误: {type(result)}, 应返回 dict"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def register_tool(
        self,
        tool_name: str,
        tool_info: Dict
    ):
        """注册工具到注册表"""
        registry = self._load_registry()
        registry[tool_name] = {
            **tool_info,
            "registered_at": datetime.now().isoformat()
        }
        self._save_registry(registry)

    def list_tools(self) -> List[str]:
        """列出所有已注册的工具"""
        registry = self._load_registry()
        return list(registry.keys())

    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """获取工具信息"""
        registry = self._load_registry()
        return registry.get(tool_name)

    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用"""
        tool_path = self.tools_dir / f"{tool_name}.py"
        return tool_path.exists()

    def discover_tools(self, base_dir: str = "./tools") -> List[str]:
        """发现所有可用工具"""
        discovered = []
        base_path = Path(base_dir)

        for py_file in base_path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            tool_name = py_file.stem
            if self._check_execute_function(py_file):
                discovered.append(tool_name)

        return discovered
