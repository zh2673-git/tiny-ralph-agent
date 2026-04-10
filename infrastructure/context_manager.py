"""
上下文管理器 - 智能管理上下文窗口，防止溢出

职责：
1. 上下文窗口监控 - 实时跟踪上下文使用率
2. 溢出检测 - 接近阈值时触发策略
3. 摘要压缩 - 对旧消息进行摘要而非直接丢弃
4. 智能截断 - 保留关键信息
"""

import os
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Literal
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


class CompressionStrategy(Enum):
    """压缩策略"""
    NONE = "none"
    TRUNCATE = "truncate"
    SUMMARIZE = "summarize"
    HYBRID = "hybrid"


@dataclass
class ContextStats:
    """上下文统计"""
    current_tokens: int = 0
    max_tokens: int = 4096
    warning_threshold: float = 0.7
    danger_threshold: float = 0.9

    @property
    def usage_ratio(self) -> float:
        return self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0

    @property
    def warning_level(self) -> Literal["normal", "warning", "danger"]:
        ratio = self.usage_ratio
        if ratio >= self.danger_threshold:
            return "danger"
        elif ratio >= self.warning_threshold:
            return "warning"
        return "normal"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_tokens": self.current_tokens,
            "max_tokens": self.max_tokens,
            "usage_ratio": f"{self.usage_ratio:.1%}",
            "warning_level": self.warning_level
        }


@dataclass
class MessageWithMetadata:
    """带元数据的消息"""
    message: BaseMessage
    tokens: int
    timestamp: float = field(default_factory=time.time)
    is_tool_result: bool = False
    tool_name: Optional[str] = None
    importance: float = 1.0


class ContextManager:
    """
    上下文管理器

    设计原则：
    1. 不重复造轮子 - 复用 OllamaRuntime 的 tokenize 方法
    2. 渐进式压缩 - warning 时摘要，danger 时截断
    3. 保留关键信息 - 工具结果 > 系统提示 > 对话历史
    4. 可插拔 - 支持自定义摘要函数
    """

    def __init__(
        self,
        ollama_runtime=None,
        warning_threshold: float = 0.7,
        danger_threshold: float = 0.9,
        max_summary_length: int = 200,
    ):
        self._runtime = ollama_runtime
        self._warning_threshold = warning_threshold
        self._danger_threshold = danger_threshold
        self._max_summary_length = max_summary_length
        self._stats = ContextStats(
            warning_threshold=warning_threshold,
            danger_threshold=danger_threshold
        )
        self._messages: List[MessageWithMetadata] = []
        self._summary_func: Optional[Callable[[str], str]] = None

    def set_ollama_runtime(self, runtime):
        """设置 Ollama 运行时"""
        self._runtime = runtime

    def set_summary_function(self, func: Callable[[str], str]):
        """设置自定义摘要函数"""
        self._summary_func = func

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        if self._runtime:
            try:
                return self._runtime.count_tokens(text)
            except Exception:
                pass
        return len(text) // 4

    def count_message_tokens(self, message: BaseMessage) -> int:
        """计算单条消息的 token 数"""
        content = message.content if hasattr(message, 'content') else str(message)
        return self.estimate_tokens(content)

    def _classify_message(self, message: BaseMessage) -> tuple[bool, Optional[str]]:
        """分类消息，返回 (是否工具结果, 工具名)"""
        content = message.content if hasattr(message, 'content') else ""

        tool_indicators = [
            "🔧 执行", "✅ 结果", "🔍 搜索结果", "📊 查询结果",
            "工具:", "执行 →", "Search results:", "Result:"
        ]

        for indicator in tool_indicators:
            if indicator in content:
                return True, self._extract_tool_name(content, indicator)

        return False, None

    def _extract_tool_name(self, content: str, indicator: str) -> Optional[str]:
        """提取工具名称"""
        idx = content.find(indicator)
        if idx >= 0:
            remaining = content[idx + len(indicator):]
            for line in remaining.split('\n'):
                line = line.strip()
                if line and not line.startswith("状态:"):
                    return line.split()[0] if line.split() else "unknown"
        return None

    def add_message(self, message: BaseMessage) -> None:
        """添加消息"""
        is_tool, tool_name = self._classify_message(message)
        tokens = self.count_message_tokens(message)

        importance = 0.5
        if isinstance(message, SystemMessage):
            importance = 0.8
        elif is_tool:
            importance = 1.0
        elif isinstance(message, AIMessage):
            importance = 0.6
        elif isinstance(message, HumanMessage):
            importance = 0.9

        self._messages.append(MessageWithMetadata(
            message=message,
            tokens=tokens,
            is_tool_result=is_tool,
            tool_name=tool_name,
            importance=importance
        ))

        self._update_stats()

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """批量添加消息"""
        for msg in messages:
            self.add_message(msg)

    def _update_stats(self) -> None:
        """更新统计信息"""
        total = sum(m.tokens for m in self._messages)
        self._stats.current_tokens = total

    def get_stats(self) -> ContextStats:
        """获取统计信息"""
        return self._stats

    def get_messages(self) -> List[BaseMessage]:
        """获取消息列表"""
        return [m.message for m in self._messages]

    def _generate_summary(self, messages: List[MessageWithMetadata]) -> str:
        """生成摘要"""
        if self._summary_func:
            contents = [m.message.content for m in messages if hasattr(m.message, 'content')]
            return self._summary_func("\n".join(contents))

        total_content = []
        for m in messages:
            if hasattr(m.message, 'content'):
                role = m.message.type if hasattr(m.message, 'type') else 'unknown'
                content = m.message.content[:100] + "..." if len(m.message.content) > 100 else m.message.content
                total_content.append(f"[{role}]: {content}")

        return f"[对话摘要 - {len(messages)} 条消息]\n" + "\n".join(total_content[-5:])

    def _compress_by_summarizing(self) -> None:
        """通过摘要压缩"""
        if len(self._messages) <= 2:
            return

        old_messages = self._messages[:-2]
        recent_messages = self._messages[-2:]

        summary = self._generate_summary(old_messages)

        summary_tokens = self.estimate_tokens(summary)

        self._messages = [
            MessageWithMetadata(
                message=SystemMessage(content=f"[早期对话摘要]\n{summary}"),
                tokens=summary_tokens,
                importance=0.3
            )
        ] + recent_messages

        self._update_stats()

    def _compress_by_truncating(self, keep_recent: int = 10) -> None:
        """直接截断，保留最近的消息"""
        if len(self._messages) <= keep_recent:
            return

        tool_results = [m for m in self._messages if m.is_tool_result]
        recent = self._messages[-keep_recent:]

        system_msgs = [m for m in self._messages if isinstance(m.message, SystemMessage)]

        self._messages = system_msgs + tool_results + recent
        self._update_stats()

    def check_and_compress(self) -> CompressionStrategy:
        """
        检查上下文并执行压缩

        Returns:
            实际使用的压缩策略
        """
        level = self._stats.warning_level

        if level == "danger":
            self._compress_by_truncating(keep_recent=6)
            return CompressionStrategy.TRUNCATE
        elif level == "warning":
            self._compress_by_summarizing()
            return CompressionStrategy.SUMMARIZE

        return CompressionStrategy.NONE

    def set_max_tokens(self, max_tokens: int) -> None:
        """设置最大 token 数"""
        self._stats.max_tokens = max_tokens

    def reset(self) -> None:
        """重置上下文"""
        self._messages.clear()
        self._stats.current_tokens = 0

    def get_early_messages(self, max_turns: int = 5) -> List[BaseMessage]:
        """获取早期消息（用于上下文窗口撑满时的处理）"""
        return self.get_messages()[:-max_turns] if len(self.get_messages()) > max_turns else []

    def get_recent_messages(self, max_turns: int = 5) -> List[BaseMessage]:
        """获取最近的消息"""
        all_msgs = self.get_messages()
        return all_msgs[-max_turns:] if len(all_msgs) > max_turns else all_msgs

    def summarize_early_context(self, llm=None) -> str:
        """
        摘要早期上下文（供 LLM 继续对话使用）

        Args:
            llm: 可选的 LLM 用于生成更好的摘要

        Returns:
            摘要字符串
        """
        early = self.get_early_messages(max_turns=10)

        if not early:
            return ""

        if llm and self._summary_func is None:
            try:
                from langchain_core.messages import HumanMessage
                prompt = f"请简要总结以下对话要点，保留关键信息（控制在100字以内）：\n\n"
                for msg in early:
                    role = getattr(msg, 'type', 'unknown')
                    content = getattr(msg, 'content', '')[:200]
                    prompt += f"{role}: {content}\n"

                response = llm.invoke([HumanMessage(content=prompt)])
                return response.content if hasattr(response, 'content') else str(response)
            except Exception:
                pass

        return self._generate_summary([
            MessageWithMetadata(message=m, tokens=self.count_message_tokens(m))
            for m in early
        ])


_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局上下文管理器实例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


def init_context_manager(
    ollama_runtime=None,
    warning_threshold: float = 0.7,
    danger_threshold: float = 0.9,
) -> ContextManager:
    """初始化全局上下文管理器"""
    global _context_manager
    _context_manager = ContextManager(
        ollama_runtime=ollama_runtime,
        warning_threshold=warning_threshold,
        danger_threshold=danger_threshold,
    )
    return _context_manager