"""
Ollama 运行时 - 本地 LLM 管理
"""

import os
import requests
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    model: str
    size: int
    size_vram: Optional[int] = None
    digest: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @property
    def size_gb(self) -> float:
        return self.size / (1024 ** 3)

    @property
    def context_window(self) -> Optional[int]:
        """从模型详情中提取上下文窗口大小"""
        if self.details:
            return self.details.get("context_window")
        return None


@dataclass
class GenerateRequest:
    """生成请求参数"""
    model: str
    prompt: str
    system: Optional[str] = None
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    num_predict: int = 256
    stop: Optional[List[str]] = None
    stream: bool = False


class OllamaRuntime:
    """
    Ollama 运行时管理

    功能：
    - 模型列表和信息
    - 动态上下文窗口检测
    - 对话生成
    - 模型管理（拉取/删除）
    """

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", self.DEFAULT_BASE_URL)
        self.default_model = default_model or os.getenv("OLLAMA_DEFAULT_MODEL", "qwen3:4b")
        self._model_cache: Dict[str, ModelInfo] = {}
        self._session_cache: Dict[str, List[BaseMessage]] = {}

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """发送请求到 Ollama API"""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", 60)
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def is_available(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            self._request("GET", "/api/tags")
            return True
        except Exception:
            return False

    def tokenize(self, text: str, model: Optional[str] = None) -> List[int]:
        """
        使用 Ollama API 获取文本的 token 列表

        Args:
            text: 要分词的文本
            model: 模型名称，默认使用 default_model

        Returns:
            token ID 列表
        """
        model = model or self.default_model
        try:
            response = self._request("POST", "/api/tokenize", json={"model": model, "content": text})
            return response.json().get("tokens", [])
        except Exception:
            return []

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """
        计算文本的 token 数量

        Args:
            text: 要计算的文本
            model: 模型名称，默认使用 default_model

        Returns:
            token 数量
        """
        return len(self.tokenize(text, model))

    def detokenize(self, tokens: List[int], model: Optional[str] = None) -> str:
        """
        将 token 列表转换回文本

        Args:
            tokens: token ID 列表
            model: 模型名称，默认使用 default_model

        Returns:
            转换后的文本
        """
        model = model or self.default_model
        try:
            response = self._request("POST", "/api/detokenize", json={"model": model, "tokens": tokens})
            return response.json().get("content", "")
        except Exception:
            return ""

    def list_models(self) -> List[ModelInfo]:
        """列出所有已下载的模型"""
        try:
            response = self._request("GET", "/api/tags")
            data = response.json()

            models = []
            for item in data.get("models", []):
                model_info = ModelInfo(
                    name=item.get("name", ""),
                    model=item.get("name", ""),
                    size=item.get("size", 0),
                    digest=item.get("digest"),
                )
                models.append(model_info)
                self._model_cache[model_info.name] = model_info

            return models
        except Exception as e:
            raise RuntimeError(f"Failed to list models: {e}")

    def get_model_info(self, model: str) -> ModelInfo:
        """获取模型详细信息（包含上下文窗口）"""
        if model in self._model_cache:
            return self._model_cache[model]

        try:
            response = self._request("POST", "/api/show", json={"name": model})
            data = response.json()

            details = data.get("details", {})
            model_info = ModelInfo(
                name=model,
                model=model,
                size=0,
                details={
                    "context_window": details.get("context_length"),
                    "model_file": data.get("model_file"),
                    "parameters": data.get("parameters"),
                    "template": data.get("template"),
                }
            )

            self._model_cache[model] = model_info
            return model_info

        except Exception as e:
            raise RuntimeError(f"Failed to get model info for {model}: {e}")

    def get_context_window(self, model: Optional[str] = None) -> int:
        """获取模型的上下文窗口大小"""
        model = model or self.default_model

        fallback_map = {
            "qwen3": 32768,
            "qwen2": 32768,
            "qwen": 8192,
            "qwen-plus": 131072,
            "qwen-max": 131072,
            "llama3": 8192,
            "llama3.1": 131072,
            "llama3.2": 131072,
            "llama2": 4096,
            "glm4": 131072,
            "glm-4": 131072,
            "mistral": 8192,
            "deepseek": 131072,
            "codellama": 16384,
            "codellama2": 16384,
        }

        try:
            info = self.get_model_info(model)
            context = info.context_window
            if context:
                return context
        except Exception:
            pass

        model_lower = model.lower()
        for prefix, ctx in fallback_map.items():
            if prefix in model_lower:
                return ctx

        return 4096

    def pull_model(self, model: str, stream: bool = True) -> Any:
        """拉取模型"""
        with requests.post(
            f"{self.base_url}/api/pull",
            json={"name": model},
            stream=stream,
            timeout=3600
        ) as response:
            response.raise_for_status()

            if stream:
                def generator():
                    for line in response.iter_lines():
                        if line:
                            yield line.decode("utf-8")
                return generator()
            else:
                return response.json()

    def delete_model(self, model: str) -> bool:
        """删除模型"""
        try:
            self._request("DELETE", "/api/delete", json={"name": model})
            if model in self._model_cache:
                del self._model_cache[model]
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to delete model {model}: {e}")

    def chat(
        self,
        messages: List[BaseMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> ChatResult:
        """
        对话生成

        Args:
            messages: 对话消息列表
            model: 模型名称，默认使用 default_model
            temperature: 温度参数
            **kwargs: 其他参数 (top_p, top_k, num_predict, stop)
        """
        model = model or self.default_model
        context_window = self.get_context_window(model)

        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        from langchain_core.outputs import ChatGeneration, ChatResult as LCChatResult

        ollama_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                ollama_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                ollama_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                ollama_messages.append({"role": "system", "content": msg.content})

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
        }

        if temperature is not None:
            payload["temperature"] = temperature
        else:
            payload["temperature"] = kwargs.get("temperature", 0.7)

        for key in ["top_p", "top_k", "num_predict", "stop"]:
            if key in kwargs:
                payload[key] = kwargs[key]

        try:
            response = self._request("POST", "/api/chat", json=payload)
            data = response.json()

            content = data.get("message", {}).get("content", "")
            generation = ChatGeneration(message=AIMessage(content=content))
            return LCChatResult(generations=[generation])

        except Exception as e:
            raise RuntimeError(f"Chat generation failed: {e}")

    def truncate_messages(
        self,
        messages: List[BaseMessage],
        model: Optional[str] = None
    ) -> List[BaseMessage]:
        """
        根据上下文窗口截断消息历史

        Args:
            messages: 原始消息列表
            model: 模型名称

        Returns:
            截断后的消息列表，保留最新的消息
        """
        model = model or self.default_model
        context_window = self.get_context_window(model)

        estimated_tokens_per_message = 50
        max_messages = context_window // estimated_tokens_per_message

        if len(messages) <= max_messages:
            return messages

        return messages[-max_messages:]

    def create_session(self, session_id: str, max_history: int = 50) -> None:
        """创建会话"""
        self._session_cache[session_id] = []

    def get_session(self, session_id: str) -> List[BaseMessage]:
        """获取会话历史"""
        return self._session_cache.get(session_id, [])

    def add_to_session(self, session_id: str, message: BaseMessage) -> None:
        """添加消息到会话"""
        if session_id not in self._session_cache:
            self.create_session(session_id)
        self._session_cache[session_id].append(message)

    def clear_session(self, session_id: str) -> None:
        """清空会话历史"""
        if session_id in self._session_cache:
            self._session_cache[session_id] = []


ollama_runtime = OllamaRuntime()
