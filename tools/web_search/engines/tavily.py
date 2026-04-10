"""
Tavily 搜索引擎
"""

import os
from typing import List, Optional
from ..engine import BaseSearchEngine, SearchResult


class TavilyEngine(BaseSearchEngine):
    """Tavily 搜索 API"""

    name = "tavily"
    api_required = True

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用 Tavily API 搜索"""
        if not self.api_key:
            raise ValueError("Tavily API key not provided")

        import requests

        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": kwargs.get("search_depth", "basic"),
            "max_results": max_results,
            "include_answer": kwargs.get("include_answer", False),
            "include_raw_content": kwargs.get("include_raw_content", False),
            "include_images": kwargs.get("include_images", False),
        }

        try:
            response = requests.post(self.base_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            results = []
            for item in result.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    engine=self.name
                ))

            return results

        except Exception as e:
            raise RuntimeError(f"Tavily search failed: {str(e)}")
