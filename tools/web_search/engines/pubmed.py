"""
PubMed 搜索引擎 - 学术论文搜索
"""

import os
from typing import List, Optional
from ..engine import BaseSearchEngine, SearchResult


class PubMedEngine(BaseSearchEngine):
    """PubMed E-utilities 学术搜索"""

    name = "pubmed"
    api_required = False

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NCBI_API_KEY")
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """使用 PubMed E-utilities 搜索学术论文"""
        import requests

        db = kwargs.get("db", "pubmed")
        retmax = min(max_results, 100)

        try:
            search_url = f"{self.base_url}/esearch.fcgi"
            search_params = {
                "db": db,
                "term": query,
                "retmax": retmax,
                "retmode": "json",
                "sort": kwargs.get("sort", "relevance")
            }

            if self.api_key:
                search_params["api_key"] = self.api_key

            search_response = requests.get(search_url, params=search_params, timeout=30)
            search_response.raise_for_status()
            search_data = search_response.json()

            id_list = search_data.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return []

            summary_url = f"{self.base_url}/esummary.fcgi"
            summary_params = {
                "db": db,
                "id": ",".join(id_list),
                "retmode": "json"
            }

            if self.api_key:
                summary_params["api_key"] = self.api_key

            summary_response = requests.get(summary_url, params=summary_params, timeout=30)
            summary_response.raise_for_status()
            summary_data = summary_response.json()

            results = []
            uids = summary_data.get("result", {}).get("uids", [])

            for uid in uids[:max_results]:
                article = summary_data.get("result", {}).get(uid, {})
                title = article.get("title", "No title")
                snippet = article.get("source", "") + " " + str(article.get("pubdate", ""))
                if article.get("authors"):
                    authors = article.get("authors")
                    author_names = [a.get("name", "") for a in authors[:3]]
                    snippet += " | Authors: " + ", ".join(author_names)
                if article.get("doi"):
                    snippet += f" | DOI: {article.get('doi')}"

                results.append(SearchResult(
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                    snippet=snippet.strip(),
                    engine=self.name
                ))

            return results

        except Exception as e:
            raise RuntimeError(f"PubMed search failed: {str(e)}")
