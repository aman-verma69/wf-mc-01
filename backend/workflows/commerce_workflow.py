"""
LlamaIndex Workflow orchestrator.

This is the real orchestration layer for the commerce system: it routes
incoming messages based on intent and on the caller's requested agent, stores
shared workflow state in the LlamaIndex Context, and dispatches to the right
specialized agent while keeping delegation bounded and auditable.
"""
from __future__ import annotations

from typing import Any

from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.analytics_agent import analytics_agent
from backend.agents.buyer_agent import buyer_agent
from backend.agents.campaign_agent import campaign_agent
from backend.agents.catalog_agent import catalog_agent
from backend.agents.customer_agent import customer_agent
from backend.agents.growth_agent import growth_agent
from backend.workflows.intent import classify_intent

AGENTS = {
    "buyer": buyer_agent,
    "catalog": catalog_agent,
    "customer": customer_agent,
    "analytics": analytics_agent,
    "growth": growth_agent,
    "campaign": campaign_agent,
}

AGENT_BY_INTENT = {
    "search_catalog": "catalog",
    "initiate_checkout": "buyer",
    "order_status": "customer",
    "analytics": "analytics",
    "growth": "growth",
    "campaign": "campaign",
    "general": "buyer",
}

MAX_DELEGATION_DEPTH = 2


class RouteEvent(Event):
    agent_key: str
    message: str
    workflow_state: dict[str, Any]


class CommerceWorkflow(Workflow):
    """Usage:
        wf = CommerceWorkflow(timeout=60)
        result = await wf.run(db=db, message=user_message, agent_key="buyer")
    """

    @staticmethod
    async def _get_state(ctx: Context) -> dict[str, Any]:
        try:
            state = await ctx.store.get("workflow_state", None)
        except ValueError:
            state = None
        if state is None:
            state = CommerceWorkflow._default_state()
        return state

    @staticmethod
    async def _get_db(ctx: Context) -> AsyncSession | None:
        try:
            return await ctx.store.get("db", None)
        except ValueError:
            return None

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "message": "",
            "customer_id": None,
            "intent": "general",
            "selected_agent": None,
            "selected_products": [],
            "products": [],
            "cart": {"items": [], "total_paise": 0},
            "order": None,
            "payment": None,
            "history": [],
            "delegation_history": [],
            "tool_trace": [],
            "workflow_turns": 0,
            "delegation_depth": 0,
            "previous_agent_outputs": [],
        }

    @staticmethod
    def _infer_agent_key(agent_key: str | None, message: str) -> str:
        candidate = (agent_key or "").strip().lower()
        if candidate and candidate in AGENTS:
            return candidate

        intent = classify_intent(agent_key, message)
        if intent in AGENT_BY_INTENT:
            return AGENT_BY_INTENT[intent]

        return "buyer"

    @step
    async def route(self, ctx: Context, ev: StartEvent) -> RouteEvent:
        db = ev.get("db")
        message = ev.get("message", "")
        agent_key = ev.get("agent_key")
        customer_id = ev.get("customer_id")

        state = await self._get_state(ctx)
        state["message"] = message
        state["customer_id"] = customer_id or state.get("customer_id")
        state["history"] = state.get("history", [])
        state["history"].append({"role": "user", "content": message})

        inferred_agent = self._infer_agent_key(agent_key, message)
        state["intent"] = classify_intent(agent_key, message)
        state["selected_agent"] = inferred_agent
        state["delegation_history"] = state.get("delegation_history", [])
        state["delegation_history"].append(
            {"from": "workflow", "to": inferred_agent, "intent": state["intent"]}
        )

        await ctx.store.set("workflow_state", state)
        await ctx.store.set("db", db)

        return RouteEvent(
            agent_key=inferred_agent,
            message=message,
            workflow_state=state,
        )

    @step
    async def dispatch(self, ctx: Context, ev: RouteEvent) -> StopEvent:
        db = await self._get_db(ctx)
        state = ev.workflow_state or await self._get_state(ctx)
        await ctx.store.set("workflow_state", state)

        if state.get("delegation_depth", 0) >= MAX_DELEGATION_DEPTH:
            return StopEvent(
                result={
                    "agent": ev.agent_key,
                    "reply": "The workflow has reached its delegation limit for this request.",
                    "products": [],
                    "workflow_state": state,
                    "ok": False,
                    "error": "delegation_limit_reached",
                }
            )

        if ev.agent_key not in AGENTS:
            raise ValueError(f"Unknown agent_key: {ev.agent_key}. Valid: {list(AGENTS)}")

        state["delegation_depth"] = int(state.get("delegation_depth", 0)) + 1
        state["workflow_turns"] = int(state.get("workflow_turns", 0)) + 1
        state["selected_agent"] = ev.agent_key
        await ctx.store.set("workflow_state", state)

        agent = AGENTS[ev.agent_key]
        result = await agent.run(db, ev.message, history=state.get("history", []), workflow_state=state)

        state["history"] = state.get("history", [])
        state["history"].append({"role": "assistant", "content": result.get("reply", "")})
        state["selected_products"] = result.get("products", [])
        state["products"] = result.get("products", [])
        if result.get("products"):
            state["cart"]["items"] = result["products"]
        state["last_agent"] = ev.agent_key
        state["last_result"] = result
        state["previous_agent_outputs"] = state.get("previous_agent_outputs", [])
        state["previous_agent_outputs"].append({"agent": ev.agent_key, "result": result})
        await ctx.store.set("workflow_state", state)

        return StopEvent(
            result={
                "agent": ev.agent_key,
                "reply": result.get("reply", ""),
                "products": result.get("products", []),
                "workflow_state": state,
                "ok": True,
                "error": None,
            }
        )
