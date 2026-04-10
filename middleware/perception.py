"""
感知中间件 - 封装业务感知逻辑
"""

from typing import Dict, Any, List, Literal
from langgraph.types import Command
import logging

logger = logging.getLogger("middleware.perception")


class PerceptionMiddleware:
    def __init__(
        self,
        subscribed_sources: List[str] = None,
        filter_rules: List[callable] = None,
        perception_window: int = 100
    ):
        self.subscribed_sources = subscribed_sources or ["user_input"]
        self.filter_rules = filter_rules or [(lambda x: bool(x))]
        self.perception_window = perception_window
        self.raw_data_buffer: List[Any] = []

    def __call__(self, state: Dict[str, Any]) -> Command[Literal["decision"]]:
        messages = state.get("messages", [])
        user_input = self._extract_latest_input(messages)

        if not user_input:
            return Command(
                update={"perception_result": {"status": "no_input", "content": ""}},
                goto="decision"
            )

        perceived_data = self._sense(user_input, state)
        filtered_data = self._filter(perceived_data)
        self._store(filtered_data)

        perception_result = {
            "status": "success",
            "content": user_input,
            "perceived_data": filtered_data,
            "sources": self.subscribed_sources
        }

        print(f"\n📥 感知 → 输入: {user_input[:50]}{'...' if len(user_input) > 50 else ''}")

        return Command(
            update={
                "perception_result": perception_result,
                "goal": perception_result.get("content", user_input)
            },
            goto="decision"
        )

    def _extract_latest_input(self, messages: List[Any]) -> str:
        if not messages:
            return ""
        for msg in reversed(messages):
            if hasattr(msg, 'type'):
                if msg.type == "human" or getattr(msg, 'role', '') == "user":
                    return getattr(msg, 'content', '')
            elif isinstance(msg, dict):
                if msg.get("role") == "user":
                    return msg.get("content", "")
        return ""

    def _sense(self, user_input: str, state: Dict[str, Any]) -> List[Any]:
        results = []
        for source in self.subscribed_sources:
            data = self._fetch_from_source(source, user_input, state)
            results.extend(data)
        return results

    def _fetch_from_source(self, source: str, user_input: str, state: Dict[str, Any]) -> List[Any]:
        if source == "user_input":
            return [{"type": "user_input", "content": user_input}]
        elif source == "file_system":
            return self._fetch_files(user_input)
        elif source == "current_directory":
            return self._fetch_current_directory()
        elif source == "context":
            return [{"type": "context", "content": state.get("context", {})}]
        return []

    def _fetch_files(self, pattern: str) -> List[Any]:
        import glob
        results = []
        try:
            files = glob.glob(pattern, recursive=True)
            for f in files[:10]:
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        content = fp.read(1000)
                        results.append({"type": "file", "path": f, "content": content})
                except:
                    pass
        except Exception as e:
            logger.warning(f"获取文件失败: {e}")
        return results

    def _fetch_current_directory(self) -> List[Any]:
        import os
        try:
            entries = os.listdir(".")
            return [{"type": "directory", "content": str(entries[:20])}]
        except:
            return []

    def _filter(self, data: List[Any]) -> List[Any]:
        for rule in self.filter_rules:
            data = [d for d in data if rule(d)]
        return data

    def _store(self, data: List[Any]):
        self.raw_data_buffer.extend(data)
        if len(self.raw_data_buffer) > self.perception_window:
            self.raw_data_buffer = self.raw_data_buffer[-self.perception_window:]

    def get_system_prompt(self) -> str:
        return """你是一个智能助手，可以帮助用户分析文件、执行命令和解决问题。"""
