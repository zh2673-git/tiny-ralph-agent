"""
Bing 搜索引擎 - 微软搜索 API
"""

import os
from typing import List, Optional
from ..engine import BaseSearchEngine, SearchResult


class BingEngine(BaseSearchEngine):
    """Bing Search API v7"""

    name = "bing"
    api_required = True

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BING_API_KEY")
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用 Bing Search API 搜索"""
        import requests

        if not self.api_key:
            raise ValueError("Bing API key not provided")

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }

        params = {
            "q": query,
            "count": min(max_results, 50),
            "offset": kwargs.get("offset", 0),
            "mkt": kwargs.get("mkt", "en-US"),
            "safesearch": kwargs.get("safesearch", "Moderate"),
        }

        try:
            response = requests.get(
                self.base_url,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            results = []
            web_pages = result.get("webPages", {}).get("value", [])

            for item in web_pages[:max_results]:
                results.append(SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    engine=self.name
                ))

            return results

        except Exception as e:
            raise RuntimeError(f"Bing search failed: {str(e)}")
