"""记忆基础设施 - 直接使用 LangChain"""

from langgraph.checkpoint.memory import MemorySaver


def create_checkpointer():
    """
    创建检查点存储

    直接使用 LangGraph 基础设施
    """
    return MemorySaver()
