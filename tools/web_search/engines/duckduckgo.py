"""
DuckDuckGo 搜索引擎 - 免费无需 API Key
"""

from typing import List
from ..engine import BaseSearchEngine, SearchResult


class DuckDuckGoEngine(BaseSearchEngine):
    """DuckDuckGo HTML 搜索 (无需 API Key)"""

    name = "duckduckgo"
    api_required = False

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用 DuckDuckGo HTML 搜索"""
        import requests
        from bs4 import BeautifulSoup

        params = {
            "q": query,
            "kl": kwargs.get("kl", "wt-wt"),
        }

        try:
            response = requests.get(
                "https://duckduckgo.com/html/",
                params=params,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 Agent/1.0"}
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            for result in soup.select(".result")[:max_results]:
                title_elem = result.select_one(".result__a")
                snippet_elem = result.select_one(".result__snippet")
                url_elem = result.select_one("a")

                if title_elem:
                    results.append(SearchResult(
                        title=title_elem.get_text(strip=True),
                        url=title_elem.get("href", ""),
                        snippet=snippet_elem.get_text(strip=True) if snippet_elem else "",
                        engine=self.name
                    ))

            return results

        except Exception as e:
            raise RuntimeError(f"DuckDuckGo search failed: {str(e)}")
