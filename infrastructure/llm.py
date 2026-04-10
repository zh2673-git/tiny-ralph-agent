"""LLM 基础设施 - 直接使用 LangChain"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


def create_llm(config: dict) -> BaseChatModel:
    """
    创建 LLM 实例

    直接使用 LangChain 的 init_chat_model，
    不再封装 LLMService 类
    """
    return init_chat_model(
        model=config.get("model", "qwen3.5:4b"),
        model_provider=config.get("provider", "ollama"),
        temperature=config.get("temperature", 0.7),
        base_url=config.get("base_url", "http://localhost:11434"),
    )
