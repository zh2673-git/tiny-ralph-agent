"""
搜索文件工具
"""

import glob
from langchain_core.tools import tool


@tool
def search_files(pattern: str) -> str:
    """搜索匹配模式的文件

    Args:
        pattern: 文件匹配模式，如 "**/*.py"、"src/**/*.ts"

    Returns:
        匹配的文件列表，每行一个，最多返回 50 个
    """
    try:
        files = glob.glob(pattern, recursive=True)
        if not files:
            return "No files found."
        return "\n".join(files[:50])
    except Exception as e:
        return f"Error searching files: {str(e)}"
