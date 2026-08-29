"""
Tavily web search — used by Catalog (product/competitor research) and
Growth (market trend lookups) agents. Never used near the payment path.

Requires: pip install tavily-python
Requires env var: TAVILY_API_KEY (https://app.tavily.com)
"""
from tavily import TavilyClient

from backend.config.settings import get_settings

settings = get_settings()

_client: TavilyClient | None = None


def get_tavily_client() -> TavilyClient:
    global _client
    if _client is None:
        if not settings.TAVILY_API_KEY:
            raise RuntimeError("TAVILY_API_KEY is not set — add it to .env (see .env.example).")
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


def search(query: str, max_results: int = 5, search_depth: str = "basic") -> dict:
    client = get_tavily_client()
    return client.search(query=query, max_results=max_results, search_depth=search_depth)
