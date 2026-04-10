"""
Code Review Lint Script
简单的代码质量检查脚本
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Any


def lint_python_file(file_path: str) -> Dict[str, Any]:
    """对 Python 文件进行静态 lint 检查"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        issues = []
        lines = content.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not ast.get_docstring(node):
                    issues.append({
                        "type": "missing_docstring",
                        "location": f"{file_path}:{node.lineno}",
                        "message": f"函数 '{node.name}' 缺少文档字符串"
                    })

                if len([n for n in ast.walk(node)]) > 50:
                    issues.append({
                        "type": "high_complexity",
                        "location": f"{file_path}:{node.lineno}",
                        "message": f"函数 '{node.name}' 复杂度较高"
                    })

        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({
                    "type": "line_too_long",
                    "location": f"{file_path}:{i}",
                    "message": f"行超过120字符 (当前{len(line)})"
                })

            if line.rstrip() != line:
                issues.append({
                    "type": "trailing_whitespace",
                    "location": f"{file_path}:{i}",
                    "message": "行尾有空白字符"
                })

        return {
            "file": file_path,
            "issues_count": len(issues),
            "issues": issues,
            "status": "ok" if len(issues) == 0 else "warnings"
        }

    except Exception as e:
        return {
            "file": file_path,
            "error": str(e),
            "status": "error"
        }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = lint_python_file(sys.argv[1])
        print(result)
