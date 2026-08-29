"""
Grok via x.ai's OpenAI-compatible API.
Requires: pip install openai
Requires env var: XAI_API_KEY (https://console.x.ai)
"""
from openai import AsyncOpenAI

from backend.config.settings import get_settings

settings = get_settings()

_client: AsyncOpenAI | None = None


def get_grok_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.XAI_API_KEY:
            raise RuntimeError("XAI_API_KEY is not set — add it to .env (see .env.example).")
        _client = AsyncOpenAI(api_key=settings.XAI_API_KEY, base_url=settings.XAI_BASE_URL)
    return _client


async def grok_chat(messages: list[dict], tools: list[dict] | None = None, **kwargs) -> dict:
    client = get_grok_client()
    response = await client.chat.completions.create(
        model=settings.XAI_MODEL,
        messages=messages,
        tools=tools,
        **kwargs,
    )
    return response.model_dump()
