"""
分析代码结构工具
"""

from typing import Dict, Any
from langchain_core.tools import tool


@tool
def analyze_code_structure(file_path: str) -> Dict[str, Any]:
    """分析代码文件结构

    Args:
        file_path: 代码文件路径

    Returns:
        包含代码结构信息的字典:
        - total_lines: 总行数
        - file_path: 文件路径
        - has_functions: 是否包含函数定义
        - has_classes: 是否包含类定义
        - imports: 导入语句列表
        - language: 推测的编程语言
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')

        result = {
            "total_lines": len(lines),
            "file_path": file_path,
            "has_functions": 'def ' in content,
            "has_classes": 'class ' in content,
            "imports": [line.strip() for line in lines if line.strip().startswith('import ') or line.strip().startswith('from ')],
        }

        ext = file_path.split('.')[-1].lower()
        lang_map = {
            'py': 'Python',
            'js': 'JavaScript',
            'ts': 'TypeScript',
            'java': 'Java',
            'go': 'Go',
            'rs': 'Rust',
            'cpp': 'C++',
            'c': 'C',
            'md': 'Markdown',
            'json': 'JSON',
            'yaml': 'YAML',
            'yml': 'YAML',
        }
        result["language"] = lang_map.get(ext, 'Unknown')

        return result
    except Exception as e:
        return {"error": str(e)}
