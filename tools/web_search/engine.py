"""
搜索引擎基类 - 定义引擎接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    engine: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "engine": self.engine
        }


class BaseSearchEngine(ABC):
    """搜索引擎基类"""

    name: str = "base"
    api_required: bool = False

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """
        执行搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            **kwargs: 引擎特定参数

        Returns:
            搜索结果列表
        """
        pass

    def format_results(self, results: List[SearchResult]) -> str:
        """格式化搜索结果为字符串"""
        if not results:
            return "No results found."

        lines = []
        for i, result in enumerate(results, 1):
            lines.append(f"[{i}] {result.title}")
            lines.append(f"    URL: {result.url}")
            lines.append(f"    {result.snippet}")
            lines.append("")

        return "\n".join(lines)

    def is_available(self, api_key: Optional[str] = None) -> bool:
        """检查引擎是否可用"""
        if self.api_required:
            return bool(api_key)
        return True
