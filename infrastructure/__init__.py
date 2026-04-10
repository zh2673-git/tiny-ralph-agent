"""基础设施层"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from .llm import OllamaRuntime, ModelInfo, LLMRegistry, ModelConfig
from .llm.ollama import ollama_runtime
from .llm.registry import llm_registry
from .context import SystemContext, create_runnable_config
from .context_manager import (
    ContextManager,
    ContextStats,
    CompressionStrategy,
    get_context_manager,
    init_context_manager,
)
from .memory import create_checkpointer
from .skill_loader import SkillLoader, Skill, create_template_skill


def create_llm(config: dict) -> BaseChatModel:
    """创建 LLM 实例"""
    return init_chat_model(
        model=config.get("model", "qwen3.5:4b"),
        model_provider=config.get("provider", "ollama"),
        temperature=config.get("temperature", 0.7),
        base_url=config.get("base_url", "http://localhost:11434"),
    )


__all__ = [
    "create_llm",
    "OllamaRuntime",
    "ModelInfo",
    "LLMRegistry",
    "ModelConfig",
    "ollama_runtime",
    "llm_registry",
    "SystemContext",
    "create_runnable_config",
    "ContextManager",
    "ContextStats",
    "CompressionStrategy",
    "get_context_manager",
    "init_context_manager",
    "create_checkpointer",
    "SkillLoader",
    "Skill",
    "create_template_skill",
]
