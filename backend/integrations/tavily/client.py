"""
Tavily web search — used by Catalog (product/competitor research) and
Growth (market trend lookups) agents. Never used near the payment path.

Requires: pip install tavily-python
Requires env var: TAVILY_API_KEY (https://app.tavily.com)
"""
import logging
import time

import requests
from tavily import TavilyClient

from backend.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_client: TavilyClient | None = None


def get_tavily_client() -> TavilyClient:
    global _client
    if _client is None:
        if not settings.TAVILY_API_KEY:
            raise RuntimeError("TAVILY_API_KEY is not set — add it to .env (see .env.example).")
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


def search(query: str, max_results: int = 5, search_depth: str = "basic", max_retries: int = 2, retry_delay: float = 0.25) -> dict:
    client = get_tavily_client()
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return client.search(query=query, max_results=max_results, search_depth=search_depth)
        except (requests.RequestException, ConnectionError, TimeoutError, OSError) as exc:
            last_error = exc
            logger.warning(
                "Tavily search failed attempt %s/%s for query=%s: %s",
                attempt + 1,
                max_retries + 1,
                query[:80],
                exc,
            )
            if attempt >= max_retries:
                break
            time.sleep(retry_delay * (attempt + 1))

    return {
        "results": [],
        "error": {
            "type": type(last_error).__name__ if last_error is not None else "SearchError",
            "message": "Live product search is temporarily unavailable. Please try again shortly.",
            "retryable": True,
            "attempts": max_retries + 1,
        },
    }
