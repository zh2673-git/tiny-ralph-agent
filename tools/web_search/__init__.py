"""Web Search Module"""

from .engine import BaseSearchEngine, SearchResult
from .main import web_search, WebSearchEngine

__all__ = [
    "BaseSearchEngine",
    "SearchResult",
    "web_search",
    "WebSearchEngine",
]
