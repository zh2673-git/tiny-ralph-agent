"""
SearXNG 搜索引擎 - 开源自托管搜索
"""

import os
from typing import List, Optional
from ..engine import BaseSearchEngine, SearchResult


class SearXNGEngine(BaseSearchEngine):
    """SearXNG 搜索 API (自托管或公共实例)"""

    name = "searxng"
    api_required = False

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("SEARXNG_URL", "https://searxng.org")

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用 SearXNG API 搜索"""
        import requests

        params = {
            "q": query,
            "format": "json",
            "engines": kwargs.get("engines", []),
            "categories": kwargs.get("categories", "general"),
        }

        if max_results:
            params["limit"] = max_results

        try:
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 Agent/1.0"}
            )
            response.raise_for_status()
            result = response.json()

            results = []
            for item in result.get("results", [])[:max_results]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    engine=self.name
                ))

            return results

        except Exception as e:
            raise RuntimeError(f"SearXNG search failed: {str(e)}")
