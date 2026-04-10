"""
LLM 注册表 - 统一管理模型配置
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(Enum):
    """模型提供商"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DASHSCOPE = "dashscope"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: ModelProvider
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: Optional[int] = None
    enabled: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        """检查模型是否可用"""
        if not self.enabled:
            return False

        if self.provider == ModelProvider.OLLAMA:
            return True

        if self.provider in (ModelProvider.OPENAI, ModelProvider.ANTHROPIC):
            return bool(self.api_key)

        if self.provider == ModelProvider.DASHSCOPE:
            return bool(self.api_key)

        return False


class LLMRegistry:
    """
    LLM 注册表

    管理所有可用的模型配置，支持：
    - 从环境变量加载
    - 从配置文件加载
    - 动态注册
    """

    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._default_model: Optional[str] = None
        self._load_from_env()

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        default_model = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen3:4b")

        self.register_model(ModelConfig(
            name="default",
            provider=ModelProvider.OLLAMA,
            model=default_model,
            base_url=ollama_base,
            context_window=self._detect_context_window(default_model, ollama_base),
        ))
        self._default_model = "default"

        if os.getenv("DASHSCOPE_API_KEY"):
            self.register_model(ModelConfig(
                name="qwen-plus",
                provider=ModelProvider.DASHSCOPE,
                model="qwen-plus",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                context_window=128 * 1024,
            ))

        if os.getenv("OPENAI_API_KEY"):
            self.register_model(ModelConfig(
                name="gpt-4o",
                provider=ModelProvider.OPENAI,
                model="gpt-4o",
                api_key=os.getenv("OPENAI_API_KEY"),
                context_window=128 * 1024,
            ))

        if os.getenv("ANTHROPIC_API_KEY"):
            self.register_model(ModelConfig(
                name="claude-3-5-sonnet",
                provider=ModelProvider.ANTHROPIC,
                model="claude-3-5-sonnet-20241022",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                context_window=200 * 1024,
            ))

    def _detect_context_window(self, model: str, base_url: str) -> int:
        """尝试检测模型的上下文窗口"""
        fallback_map = {
            "qwen3": 32768,
            "qwen2": 32768,
            "qwen": 8192,
            "qwen-plus": 128 * 1024,
            "qwen-max":  128 * 1024,
            "llama3": 8192,
            "llama3.1": 128 * 1024,
            "llama3.2": 128 * 1024,
            "llama2": 4096,
            "glm4": 128 * 1024,
            "glm-4": 128 * 1024,
            "mistral": 8192,
            "deepseek": 128 * 1024,
            "codellama": 16384,
            "codellama2": 16384,
        }

        model_lower = model.lower()
        for prefix, ctx in fallback_map.items():
            if prefix in model_lower:
                return ctx

        return 4096

    def register_model(self, config: ModelConfig) -> None:
        """注册模型"""
        self._models[config.name] = config

    def unregister_model(self, name: str) -> bool:
        """注销模型"""
        if name in self._models:
            del self._models[name]
            return True
        return False

    def get_model(self, name: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self._models.get(name)

    def list_models(self) -> List[ModelConfig]:
        """列出所有模型"""
        return list(self._models.values())

    def list_available_models(self) -> List[ModelConfig]:
        """列出所有可用的模型"""
        return [m for m in self._models.values() if m.is_available()]

    def set_default(self, name: str) -> bool:
        """设置默认模型"""
        if name in self._models:
            self._default_model = name
            return True
        return False

    @property
    def default_model(self) -> Optional[ModelConfig]:
        """获取默认模型"""
        if self._default_model:
            return self._models.get(self._default_model)
        return None


llm_registry = LLMRegistry()
