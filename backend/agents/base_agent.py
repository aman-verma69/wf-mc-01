"""
Base class for all agents. Each agent picks which LLM backend it uses
(Groq for hosted inference, gpt-oss-20B for local inference) and gets
a standard tool-calling loop.
"""

import json
from dataclasses import dataclass, field
from typing import Literal

from numpy import prod
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1 import products
from backend.integrations.llm.gpt_oss_client import gpt_oss_chat
from backend.integrations.llm.groq_client import groq_chat
from backend.services.order_service import get_customer_orders
from backend.tools.commerce_tools import TOOL_SCHEMAS, normalize_search_results, run_tool


DEFAULT_DELEGATION_RULES = {
    "buyer": {"catalog", "customer"},
    "catalog": {"buyer"},
    "customer": {"buyer"},
    "analytics": {"growth"},
    "growth": {"campaign"},
    "campaign": set(),
}


LLMBackend = Literal["groq", "gpt-oss"]


@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    backend: LLMBackend = "groq"
    delegation_scope: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=lambda: ["search_web", "initiate_checkout"])
    allowed_delegations: set[str] = field(default_factory=lambda: DEFAULT_DELEGATION_RULES["buyer"])
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

    @staticmethod
    def _is_product_search(message: str) -> bool:
        lowered = (message or "").lower()
        if not lowered:
            return False
        search_tokens = [
            "show me",
            "find",
            "search",
            "look for",
            "compare",
            "recommend",
            "under",
            "below",
            "budget",
            "headphones",
            "earbuds",
            "phone",
            "laptop",
            "shoe",
            "shirt",
        ]
        return any(token in lowered for token in search_tokens)

    def _build_delegation_request(self, target_agent: str, reason: str, task: str, context_keys: list[str] | None = None) -> dict | None:
        allowed = self.config.allowed_delegations
        if allowed is not None and target_agent not in allowed:
            return None
        return {
            "type": "delegation_request",
            "target_agent": target_agent,
            "reason": reason,
            "task": task,
            "context_keys": context_keys or [],
        }

    async def run(
        self,
        db: AsyncSession,
        user_message: str,
        history: list[dict] | None = None,
        max_turns: int = 4,
        workflow_state: dict | None = None,
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

        current_customer_id = (workflow_state or {}).get("customer_id")
        last_products = (workflow_state or {}).get("last_products") or []
        if current_customer_id or last_products:
            messages.insert(
                1,
                {
                    "role": "system",
                    "content": (
                        f"Trusted current customer_id: {current_customer_id or 'unknown'}. "
                        "Use this customer_id for cart and checkout tools. "
                        "The following are the latest discovered product candidates; "
                        "they may resolve references such as 'the first one', but they "
                        "are not in the cart unless add_to_cart is explicitly called:\n"
                        f"{json.dumps(last_products, ensure_ascii=True)}"
                    ),
                },
            )

        products: list[dict] = []
        lowered = (user_message or "").lower()

        if self.config.name == "customer_agent" and any(token in lowered for token in ["where is my order", "track my order", "status of my order", "order status", "refund", "cancel my order", "cancel order", "return my order","shipment","delivery","tracking"]):
            customer_id = (workflow_state or {}).get("customer_id")
            if db is not None and customer_id:
                orders = await get_customer_orders(db, customer_id=customer_id)
                if orders:
                    latest = orders[0]
                    reply = (
                        f"I checked the trusted order records for customer {customer_id}. "
                        f"Latest order {latest['order_id']} is in status '{latest['status']}' and the amount is ₹{latest['amount_paise'] / 100:.2f}."
                    )
                    return {
                        "status": "completed",
                        "reply": reply,
                        "products": [],
                        "ok": True,
                        "error": None,
                        "data": {"source": "trusted_order_lookup", "orders": orders},
                        "actions": ["order_status_lookup"],
                        "tool_calls": [],
                        "delegation_request": None,
                    }

                return {
                    "status": "completed",
                    "reply": "I checked the trusted order records and there are no orders on file for this customer.",
                    "products": [],
                    "ok": True,
                    "error": None,
                    "data": {"source": "trusted_order_lookup", "orders": []},
                    "actions": ["order_status_lookup"],
                    "tool_calls": [],
                    "delegation_request": None,

                }

                return {
                    "status": "failed",
                    "reply": "I couldn't look up your order because the customer session information is unavailable.",
                    "products": [],
                    "ok": False,
                    "error": "customer_context_unavailable",
                    "data": {},
                    "actions": [],
                    "tool_calls": [],
                    "delegation_request": None,
                }
            
            if search_result.get("ok"):
                search_products = search_result.get("products") or normalize_search_results(search_result.get("result"))
                if search_products:
                    products.extend(search_products)
                    valid_price_products = [p for p in products if p.get("price") is not None]
                    if valid_price_products:
                        cheapest = min(valid_price_products, key=lambda p: p.get("price") or 10**9)
                        most_expensive = max(valid_price_products, key=lambda p: p.get("price") or 0)
                        price_summary = (
                            f"Compared on price, {cheapest.get('name')} is the most affordable at ₹{cheapest.get('price')} while "
                            f"{most_expensive.get('name')} is the higher-end option at ₹{most_expensive.get('price')}."
                        )
                    else:
                        price_summary = "The available catalog evidence shows a few product candidates, but pricing details are incomplete."

                    product_names = [product.get("name") or "option" for product in products[:3]]
                    reply = (
                        f"I found {len(products)} product candidates that fit the request. "
                        f"{price_summary} For gaming, {', '.join(product_names[:2])} are the strongest current matches from the accessible product data."
                    )
                    return {
                        "status": "completed",
                        "reply": reply,
                        "products": products,
                        "ok": True,
                        "error": None,
                        "data": {"source": "search_web", "tool_trace": [{"tool": "search_web", "ok": True}]},
                        "actions": ["search_web"],
                        "tool_calls": ["search_web"],
                        "delegation_request": None,
                    }

                return {
                    "status": "completed",
                    "reply": "I found search results, but none of them were verified as individual product matches for this request.",
                    "products": [],
                    "ok": True,
                    "error": None,
                    "data": {
                        "source": "search_web",
                        "tool_trace": [{"tool": "search_web", "ok": True, "verified_products": 0}],
                    },
                    "actions": ["search_web"],
                    "tool_calls": ["search_web"],
                    "delegation_request": None,
                }

            tool_error = search_result.get("reason") or search_result.get("error_type") or "Live product search is temporarily unavailable."
            return {
                "status": "degraded",
                "reply": "I couldn’t complete the live product search right now. Please try again shortly.",
                "products": [],
                "ok": False,
                "error": search_result.get("error") or "product_search_unavailable",
                "data": {
                    "source": "search_web",
                    "tool_trace": [{"tool": "search_web", "ok": False, "error": tool_error, "retryable": search_result.get("retryable", False)}],
                },
                "actions": ["search_web_failed"],
                "tool_calls": ["search_web"],
                "delegation_request": None,
            }

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

                delegation_request = None
                if self.config.name == "buyer_agent" and any(token in lowered for token in ["where is my order", "track my order", "status of my order", "refund", "return"]):
                    delegation_request = self._build_delegation_request(
                        "customer_agent",
                        "Need current order or fulfillment status for this customer.",
                        "Look up order status or refund details for the customer.",
                        ["customer_id", "order_id"],
                    )
                elif self.config.name == "buyer_agent" and self._is_product_search(user_message) and not products:
                    delegation_request = self._build_delegation_request(
                        "catalog_agent",
                        "Need product discovery and catalog comparison before recommending an offer.",
                        "Research product options and pricing for the current shopping request.",
                        ["message", "customer_id"],
                    )

                return {
                    "status": "completed" if delegation_request is None else "delegation_required",
                    "reply": final_answer,
                    "products": products,
                    "data": {"source": "llm_response"},
                    "actions": ["respond"],
                    "tool_calls": [],
                    "delegation_request": delegation_request,
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
                    if tool_name not in self.config.allowed_tools:
                        raise ValueError(f"Tool '{tool_name}' is not allowed for {self.config.name}")

                    if current_customer_id and tool_name in {
                        "get_cart",
                        "view_cart",
                        "add_to_cart",
                        "update_cart",
                        "remove_from_cart",
                        "initiate_checkout",
                    }:
                        args["customer_id"] = current_customer_id

                    result = await run_tool(
                        db,
                        actor=self.config.name,
                        name=tool_name,
                        arguments=args,
                        delegation_scope=self.config.delegation_scope,
                    )

                    # Preserve search results for the frontend.
                    if tool_name in {"search_web", "list_catalog_products"} and result.get("ok"):
                        if tool_name == "search_web":
                            tool_products = (
                                result.get("products")
                                or normalize_search_results(result.get("result"))
                            )
                        else:
                            tool_products = result.get("products") or []

                        products.extend(tool_products)

                    if tool_name in {"get_cart", "view_cart", "add_to_cart", "update_cart", "remove_from_cart"} and result.get("cart"):
                        # Keep the conversational state aligned with the DB result.
                        if workflow_state is not None:
                            workflow_state["cart"] = result["cart"]

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
            "status": "failed",
            "reply": "I wasn't able to complete this in the allotted number of steps.",
            "products": products,
            "data": {"source": "max_tool_turns"},
            "actions": ["retry_later"],
            "tool_calls": [],
            "delegation_request": None,
        }