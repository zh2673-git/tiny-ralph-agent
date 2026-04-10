"""LLM Infrastructure Module"""

from langchain_core.language_models import BaseChatModel

from .ollama import OllamaRuntime, ModelInfo
from .registry import LLMRegistry, ModelConfig

def create_llm(config: dict) -> BaseChatModel:
    """创建 LLM 实例"""
    from langchain.chat_models import init_chat_model
    return init_chat_model(
        model=config.get("model", "qwen3.5:4b"),
        model_provider=config.get("provider", "ollama"),
        temperature=config.get("temperature", 0.7),
        base_url=config.get("base_url", "http://localhost:11434"),
    )


class TokenManager:
    """
    Token 管理器 - 基础设施层

    使用业内标准估算公式：
    - 1 token ≈ 4 字符（GPT 时代广泛使用的粗略估算）

    不调用 API，避免额外延迟开销。
    """

    def __init__(self, context_window: int = 4096, model: str = "qwen3.5:4b"):
        self.context_window = context_window
        self.model = model
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量

        业界标准：1 token ≈ 4 字符（对于中文/英文混合文本）
        这是 ChatGPT 时代广泛使用的粗略估算，误差约 10-20%
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    def count_messages_tokens(self, messages: list) -> int:
        """估算消息列表的总 token 数"""
        total = 0
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            total += self.estimate_tokens(f"{role}: {content}")
        return total

    def update(self, prompt_tokens: int = 0, completion_tokens: int = 0):
        """更新 token 计数"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens

    def reset(self):
        """重置计数"""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def remaining(self) -> int:
        """剩余上下文窗口"""
        return max(0, self.context_window - self.total_tokens)

    def usage_ratio(self) -> float:
        """使用比例"""
        if self.context_window == 0:
            return 0.0
        return self.total_tokens / self.context_window

    def warning_level(self) -> str:
        """警告级别：normal / warning / danger"""
        ratio = self.usage_ratio()
        if ratio < 0.7:
            return "normal"
        elif ratio < 0.9:
            return "warning"
        else:
            return "danger"

    def get_context_window(self) -> int:
        """获取上下文窗口大小"""
        return self.context_window

    def __str__(self) -> str:
        remaining = self.remaining()
        return f"Used: {self.total_tokens}/{self.context_window} | Remain: {remaining}"


__all__ = [
    "OllamaRuntime",
    "ModelInfo",
    "LLMRegistry",
    "ModelConfig",
    "create_llm",
    "TokenManager",
]
