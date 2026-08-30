"""
Base class for all agents. Each agent picks which LLM backend it uses
(Groq for hosted inference, gpt-oss-20B for local inference) and gets
a standard tool-calling loop.
"""

import json
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
    delegation_scope: list[str] = field(default_factory=list)
    tool_schemas: list[dict] = field(default_factory=lambda: TOOL_SCHEMAS)


class BaseAgent:
    def __init__(self, config: AgentConfig):
        self.config = config

    async def _call_llm(self, messages: list[dict]) -> dict:
        if self.config.backend == "groq":
            return await groq_chat(
                messages,
                tools=self.config.tool_schemas,
            )

        return await gpt_oss_chat(
            messages,
            tools=self.config.tool_schemas,
        )

    async def run(
        self,
        db: AsyncSession,
        user_message: str,
        history: list[dict] | None = None,
        max_turns: int = 4,
    ) -> dict:

        messages = [
            {
                "role": "system",
                "content": self.config.system_prompt,
            }
        ]

        # Add previous conversation history safely.
        # Only role and content are sent to the LLM.
        for msg in history or []:
            role = msg.get("role")
            content = msg.get("content")

            if role in ("user", "assistant") and content is not None:
                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        # Add the current user message.
        messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        products = []

        # Tool-calling loop.
        for turn in range(max_turns):
            print(f"\n========== LLM TURN {turn + 1} ==========")

            response = await self._call_llm(messages)

            print("LLM RESPONSE:")
            print(response)

            choice = response["choices"][0]["message"]

            print("\nCHOICE:")
            print(choice)

            tool_calls = choice.get("tool_calls")

            print("\nTOOL CALLS:")
            print(tool_calls)

            # No tool call means the LLM has produced its final answer.
            if not tool_calls:
                final_answer = choice.get("content") or ""

                print("\nFINAL ANSWER:")
                print(final_answer)
                print("========================================\n")

                return {
                    "reply": final_answer,
                    "products": products,
                }

            # IMPORTANT:
            # Do not append the complete Groq response message directly.
            # It may contain unsupported fields such as annotations.
            assistant_message = {
                "role": "assistant",
                "content": choice.get("content"),
                "tool_calls": tool_calls,
            }

            messages.append(assistant_message)

            # Execute every requested tool.
            for call in tool_calls:
                tool_name = call["function"]["name"]

                try:
                    args = json.loads(
                        call["function"]["arguments"]
                    )
                except json.JSONDecodeError as e:
                    print(f"\nINVALID TOOL ARGUMENTS: {e}")

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(
                                {
                                    "error": "Invalid tool arguments",
                                    "details": str(e),
                                }
                            ),
                        }
                    )
                    continue

                print("\nTOOL NAME:")
                print(tool_name)

                print("\nTOOL ARGS:")
                print(args)

                try:
                    result = await run_tool(
                        db,
                        actor=self.config.name,
                        name=tool_name,
                        arguments=args,
                    )

                     # Preserve search results for the frontend.
                    if tool_name == "search_web" and result.get("ok"):
                        search_data = result.get("result", {})

                        for item in search_data.get("results", []):
                            products.append(
                                {
                                    "name": item.get("title", "Unknown product"),
                                    "price": None,
                                    "image_url": None,
                                    "url": item.get("url"),
                                }
                            )

                    print("\nTOOL RESULT:")
                    print(result)

                except Exception as e:
                    print("\nTOOL ERROR:")
                    print(str(e))

                    result = {
                        "error": str(e),
                    }

                # Send the tool result back to the LLM.
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result),
                    }
                )

            print("========================================")

        print("\nMAXIMUM TOOL TURNS REACHED\n")

        return {
            "reply": "I wasn't able to complete this in the allotted number of steps.",
            "products": products,
        }