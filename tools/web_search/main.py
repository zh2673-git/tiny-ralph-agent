"""
Web Search 统一入口 - 自动选择引擎 + 智能降级
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool

from .engine import BaseSearchEngine, SearchResult
from ..base import SearchEngineRegistry, QuotaManager


SPECIALIZED_ENGINES = {
    "github": ["github", "code", "repository", "repo", "commit", "pull request", "issue", "stars", "仓库", "代码"],
    "pubmed": ["pubmed", "paper", "research", "academic", "scholar", "citation", "doi", "论文", "学术", "研究"],
}


class WebSearchEngine:
    """Web Search 引擎管理器"""

    def __init__(self):
        self.api_keys = SearchEngineRegistry.get_api_keys()
        self.quota_manager = QuotaManager()

    def _get_engine(self, name: str) -> BaseSearchEngine:
        """根据名称获取引擎实例"""
        if name == "tavily":
            from .engines.tavily import TavilyEngine
            return TavilyEngine(self.api_keys.get("tavily"))
        elif name == "searxng":
            from .engines.searxng import SearXNGEngine
            return SearXNGEngine(self.api_keys.get("searxng"))
        elif name == "duckduckgo":
            from .engines.duckduckgo import DuckDuckGoEngine
            return DuckDuckGoEngine()
        elif name == "bing":
            from .engines.bing import BingEngine
            return BingEngine(self.api_keys.get("bing"))
        elif name == "github":
            from .engines.github import GitHubEngine
            return GitHubEngine(self.api_keys.get("github"))
        elif name == "pubmed":
            from .engines.pubmed import PubMedEngine
            return PubMedEngine(self.api_keys.get("pubmed"))
        else:
            raise ValueError(f"Unknown engine: {name}")

    def _auto_select_engine(self, query: str) -> str:
        """根据查询内容自动选择最合适的引擎"""
        query_lower = query.lower()

        for engine_name, keywords in SPECIALIZED_ENGINES.items():
            if any(kw in query_lower for kw in keywords):
                if engine_name in self.api_keys or not self._get_engine(engine_name).api_required:
                    return engine_name

        return "auto"

    def search(
        self,
        query: str,
        engine: str = "auto",
        max_results: int = 10,
        fallback: bool = True,
        **kwargs
    ) -> str:
        """
        执行搜索，自动选择引擎或降级

        Args:
            query: 搜索关键词
            engine: 指定引擎，"auto" 表示自动选择
            max_results: 最大结果数
            fallback: 是否启用降级（引擎失败时尝试其他引擎）
            **kwargs: 引擎特定参数

        Returns:
            格式化后的搜索结果字符串
        """
        if engine == "auto":
            selected_engine = self._auto_select_engine(query)
            if selected_engine != "auto":
                eng_config = SearchEngineRegistry.get_engine(selected_engine)
                if eng_config and eng_config.is_available(self.api_keys):
                    engines_to_try = [eng_config]
                else:
                    engines_to_try = SearchEngineRegistry.get_available_engines(self.api_keys)
            else:
                engines_to_try = SearchEngineRegistry.get_available_engines(self.api_keys)
        else:
            eng_config = SearchEngineRegistry.get_engine(engine)
            if not eng_config:
                return f"Unknown engine: {engine}"
            engines_to_try = [eng_config]

        errors = []

        for eng_config in engines_to_try:
            try:
                if not self.quota_manager.is_available(eng_config.name):
                    errors.append(f"{eng_config.name}: quota exhausted")
                    continue

                search_engine = self._get_engine(eng_config.name)

                if not search_engine.is_available(self.api_keys.get(eng_config.name)):
                    errors.append(f"{eng_config.name}: not configured")
                    continue

                results = search_engine.search(query, max_results, **kwargs)
                self.quota_manager.use(eng_config.name)

                return search_engine.format_results(results)

            except Exception as e:
                errors.append(f"{eng_config.name}: {str(e)}")
                if not fallback:
                    break
                continue

        if errors:
            return f"Search failed. Errors:\n" + "\n".join(f"- {e}" for e in errors)

        return "No search engines available."


web_search_instance = WebSearchEngine()


@tool
def web_search(query: str, engine: str = "auto") -> str:
    """
    网络搜索工具 - 自动选择可用引擎

    支持的引擎（按优先级）:
    1. tavily - 需要 TAVILY_API_KEY (免费额度 1000次/月)
    2. searxng - 需要 SEARXNG_URL 环境变量 (自托管或公共实例)
    3. duckduckgo - 免费无需配置

    Args:
        query: 搜索关键词
        engine: 搜索引擎，"auto" 表示自动选择最高优先级可用引擎

    Returns:
        格式化后的搜索结果，包含标题、URL和摘要
    """
    return web_search_instance.search(query, engine=engine)
