"""
gpt-oss-20B — an open-weight model with NO hosted API from OpenAI/Anthropic.
You must self-host it (vLLM, Ollama, TGI, etc.) and point GPT_OSS_BASE_URL
at that server. This client just assumes an OpenAI-compatible /v1 endpoint,
which vLLM and Ollama both provide out of the box.

Example self-host with Ollama:
  ollama pull gpt-oss:20b
  ollama serve   # exposes http://localhost:11434/v1

Example with vLLM:
  vllm serve openai/gpt-oss-20b --port 8000
  # then set GPT_OSS_BASE_URL=http://localhost:8000/v1
"""
from openai import AsyncOpenAI

from backend.config.settings import get_settings

settings = get_settings()

_client: AsyncOpenAI | None = None


def get_gpt_oss_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # api_key can be a dummy string if your local server doesn't check it
        _client = AsyncOpenAI(api_key=settings.GPT_OSS_API_KEY or "not-needed", base_url=settings.GPT_OSS_BASE_URL)
    return _client


async def gpt_oss_chat(messages: list[dict], tools: list[dict] | None = None, **kwargs) -> dict:
    client = get_gpt_oss_client()
    response = await client.chat.completions.create(
        model=settings.GPT_OSS_MODEL,
        messages=messages,
        tools=tools,
        **kwargs,
    )
    return response.model_dump()
