"""
读取项目文件工具
"""

from langchain_core.tools import tool


@tool
def read_project_file(file_path: str) -> str:
    """读取项目文件

    Args:
        file_path: 文件路径（绝对路径或相对于当前工作目录）

    Returns:
        文件内容，失败时返回错误信息
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"
