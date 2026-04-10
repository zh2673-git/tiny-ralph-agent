"""
GitHub 搜索引擎 - 代码和仓库搜索
"""

import os
from typing import List, Optional
from ..engine import BaseSearchEngine, SearchResult


class GitHubEngine(BaseSearchEngine):
    """GitHub REST API 搜索"""

    name = "github"
    api_required = False

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用 GitHub API 搜索代码/仓库"""
        import requests

        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.api_key:
            headers["Authorization"] = f"token {self.api_key}"

        search_type = kwargs.get("type", "repositories")

        try:
            response = requests.get(
                f"{self.base_url}/search/{search_type}",
                params={"q": query, "per_page": max_results},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            results = []
            items = result.get("items", [])

            for item in items[:max_results]:
                if search_type == "repositories":
                    results.append(SearchResult(
                        title=item.get("full_name", ""),
                        url=item.get("html_url", ""),
                        snippet=f"⭐ {item.get('stargazers_count', 0)} | {item.get('language', 'N/A')} | {item.get('description', 'No description')}",
                        engine=self.name
                    ))
                elif search_type == "code":
                    results.append(SearchResult(
                        title=item.get("name", ""),
                        url=item.get("html_url", ""),
                        snippet=f"Repo: {item.get('repository', {}).get('full_name', '')} | {item.get('path', '')}",
                        engine=self.name
                    ))

            return results

        except Exception as e:
            raise RuntimeError(f"GitHub search failed: {str(e)}")
