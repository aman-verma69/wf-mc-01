"""
Base class for all agents. Each agent picks which LLM backend it uses
(Groq for reasoning-heavy agents, gpt-oss-20B for cheaper/simpler ones —
adjust per your cost/latency needs) and gets a standard tool-calling loop.
"""
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.llm.gpt_oss_client import gpt_oss_chat
from backend.integrations.llm.groq_client import groq_chat
from backend.tools.commerce_tools import TOOL_SCHEMAS, run_tool

LLMBackend = Literal["groq", "gpt-oss"]


@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    backend: LLMBackend = "groq"
    delegation_scope: list[str] = field(default_factory=list)  # e.g. ["checkout"] for buyer_agent
    tool_schemas: list[dict] = field(default_factory=lambda: TOOL_SCHEMAS)


class BaseAgent:
    def __init__(self, config: AgentConfig):
        self.config = config

    async def _call_llm(self, messages: list[dict]) -> dict:
        if self.config.backend == "groq":
            return await groq_chat(messages, tools=self.config.tool_schemas)
        return await gpt_oss_chat(messages, tools=self.config.tool_schemas)

    async def run(self, db: AsyncSession, user_message: str, history: list[dict] | None = None, max_turns: int = 4) -> str:
        """Standard tool-calling loop: ask the LLM, execute any tool calls
        it requests, feed results back, repeat until it answers in plain text.
        """
        messages = [{"role": "system", "content": self.config.system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_message})

        for _ in range(max_turns):
            response = await self._call_llm(messages)
            choice = response["choices"][0]["message"]
            tool_calls = choice.get("tool_calls")

            if not tool_calls:
                return choice["content"] or ""

            messages.append(choice)
            for call in tool_calls:
                import json
                args = json.loads(call["function"]["arguments"])
                result = await run_tool(db, actor=self.config.name, name=call["function"]["name"], arguments=args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result),
                })

        return "I wasn't able to complete this in the allotted number of steps."
