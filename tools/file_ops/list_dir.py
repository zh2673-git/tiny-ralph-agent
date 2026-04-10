"""
列出目录内容工具
"""

import os
from langchain_core.tools import tool


@tool
def list_directory(directory: str = ".") -> str:
    """列出目录内容

    Args:
        directory: 目录路径（绝对路径或相对路径），默认为当前目录

    Returns:
        目录中的文件列表，每行一个
    """
    try:
        items = os.listdir(directory)
        return "\n".join(sorted(items))
    except Exception as e:
        return f"Error listing directory: {str(e)}"
