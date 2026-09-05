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
from backend.services.cart_service import get_cart, normalize_cart
from backend.workflows import intent
from backend.workflows import intent
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
MAX_WORKFLOW_TURNS = 5
ALLOWED_DELEGATIONS = {
    "buyer": {"catalog", "customer"},
    "catalog": {"buyer"},
    "customer": {"buyer"},
    "analytics": {"growth"},
    "growth": {"campaign"},
    "campaign": set(),
}


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
            "customer": {},
            "intent": "general",
            "selected_agent": None,
            "active_agent": None,
            "completed_agents": [],
            "selected_products": [],
            "products": [],
            "last_products": [],
            "cart": {"customer_id": None, "items": [], "total_paise": 0},
            "checkout": {"amount_paise": 0, "status": "not_started", "requires_confirmation": False},
            "order": None,
            "payment": None,
            "current_action": None,
            "confirmation_status": "not_required",
            "history": [],
            "delegation_history": [],
            "tool_trace": [],
            "workflow_turns": 0,
            "delegation_depth": 0,
            "previous_agent_outputs": [],
            "errors": [],
            "status": "initialized",
            "last_action": None,
        }

    @staticmethod

    def _infer_agent_key(agent_key: str | None, intent: str) -> str:
        candidate = (agent_key or "").strip().lower()

        if candidate and candidate in AGENTS:
            return candidate

        return AGENT_BY_INTENT.get(intent, "buyer")

    @staticmethod
    def _is_delegation_allowed(source_agent: str, target_agent: str) -> bool:
        return target_agent in ALLOWED_DELEGATIONS.get(source_agent, set()) or source_agent == target_agent

    @staticmethod
    def _has_seen_delegation(state: dict[str, Any], source_agent: str, target_agent: str) -> bool:
        for item in state.get("delegation_history", []):
            if item.get("from") == source_agent and item.get("to") == target_agent:
                return True
        return False

    @step
    async def route(self, ctx: Context, ev: StartEvent) -> RouteEvent:
        db = ev.get("db")
        message = ev.get("message", "")
        agent_key = ev.get("agent_key")
        customer_id = ev.get("customer_id")

        state = await self._get_state(ctx)
        state["message"] = message
        state["customer_id"] = customer_id or state.get("customer_id")
        state["customer"] = {"customer_id": state["customer_id"], "id": state["customer_id"]}
        state["history"] = state.get("history", [])
        state["history"].append({"role": "user", "content": message})

        if customer_id and db is not None:
            state["cart"] = await get_cart(db, customer_id=customer_id)

        state["intent"] = classify_intent(agent_key, message)
        inferred_agent = self._infer_agent_key(agent_key, state["intent"])
        state["selected_agent"] = inferred_agent
        state["active_agent"] = inferred_agent
        state["status"] = "routing"
        state["last_action"] = "intent_detected"
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

        if state.get("workflow_turns", 0) >= MAX_WORKFLOW_TURNS:
            state["status"] = "failed"
            state["last_action"] = "workflow_limit_reached"
            await ctx.store.set("workflow_state", state)
            return StopEvent(
                result={
                    "agent": ev.agent_key,
                    "reply": "The workflow has reached its maximum execution turn limit for this request.",
                    "products": state.get("products", []),
                    "workflow_state": state,
                    "ok": False,
                    "error": "workflow_limit_reached",
                }
            )

        if ev.agent_key not in AGENTS:
            raise ValueError(f"Unknown agent_key: {ev.agent_key}. Valid: {list(AGENTS)}")

        state["delegation_depth"] = int(state.get("delegation_depth", 0))
        state["workflow_turns"] = int(state.get("workflow_turns", 0)) + 1
        state["selected_agent"] = ev.agent_key
        state["active_agent"] = ev.agent_key
        state["status"] = "agent_running"
        state["last_action"] = "agent_selected"
        await ctx.store.set("workflow_state", state)

        agent = AGENTS[ev.agent_key]
        result = await agent.run(db, ev.message, history=state.get("history", []), workflow_state=state)

        delegation_request = result.get("delegation_request")
        if delegation_request:
            target_agent = delegation_request.get("target_agent")
            if target_agent not in AGENTS:
                state["errors"].append({"type": "unknown_target_agent", "agent": target_agent})
                return StopEvent(result={"agent": ev.agent_key, "reply": "The requested delegated capability is not available.", "products": state.get("products", []), "workflow_state": state, "ok": False, "error": "unknown_target_agent"})

            if not self._is_delegation_allowed(ev.agent_key, target_agent):
                state["errors"].append({"type": "delegation_denied", "source": ev.agent_key, "target": target_agent})
                return StopEvent(result={"agent": ev.agent_key, "reply": "The requested delegated capability is not allowed for this workflow step.", "products": state.get("products", []), "workflow_state": state, "ok": False, "error": "delegation_denied"})

            if state.get("delegation_depth", 0) >= MAX_DELEGATION_DEPTH:
                state["errors"].append({"type": "delegation_limit_reached", "source": ev.agent_key, "target": target_agent})
                return StopEvent(result={"agent": ev.agent_key, "reply": "The workflow has reached its delegation limit for this request.", "products": state.get("products", []), "workflow_state": state, "ok": False, "error": "delegation_limit_reached"})

            if self._has_seen_delegation(state, ev.agent_key, target_agent):
                state["errors"].append({"type": "delegation_loop", "source": ev.agent_key, "target": target_agent})
                return StopEvent(result={"agent": ev.agent_key, "reply": "The workflow detected a repeated delegation loop and stopped the request.", "products": state.get("products", []), "workflow_state": state, "ok": False, "error": "delegation_loop"})

            state["delegation_depth"] = int(state.get("delegation_depth", 0)) + 1
            state["delegation_history"].append({"from": ev.agent_key, "to": target_agent, "reason": delegation_request.get("reason"), "task": delegation_request.get("task")})
            state["active_agent"] = target_agent
            state["last_action"] = "delegation_requested"
            state["history"].append({"role": "assistant", "content": result.get("reply", "")})
            await ctx.store.set("workflow_state", state)

            delegated_agent = AGENTS[target_agent]
            delegated_result = await delegated_agent.run(db, delegation_request.get("task"), history=state.get("history", []), workflow_state=state)

            state["history"].append({"role": "assistant", "content": delegated_result.get("reply", "")})
            state["selected_products"] = delegated_result.get("products", []) or result.get("products", [])
            state["products"] = state["selected_products"]
            if state["products"]:
                state["last_products"] = state["products"]
            state["completed_agents"] = list(dict.fromkeys(state.get("completed_agents", []) + [ev.agent_key, target_agent]))
            state["last_result"] = delegated_result
            state["status"] = "delegation_completed"
            state["last_action"] = "delegated_result_returned"
            await ctx.store.set("workflow_state", state)

            return StopEvent(
                result={
                    "agent": ev.agent_key,
                    "reply": delegated_result.get("reply") or result.get("reply", ""),
                    "products": state["products"],
                    "workflow_state": state,
                    "ok": delegated_result.get("ok", True),
                    "error": delegated_result.get("error"),
                }
            )

        state["history"] = state.get("history", [])
        state["history"].append({"role": "assistant", "content": result.get("reply", "")})
        state["selected_products"] = result.get("products", [])
        state["products"] = result.get("products", [])
        if result.get("products"):
            state["last_products"] = result["products"]
            state["current_action"] = "product_selected"
            state["confirmation_status"] = "not_required"

        tool_trace = result.get("data", {}).get("tool_trace") or []
        if tool_trace:
            state["tool_trace"] = state.get("tool_trace", []) + tool_trace

        state["last_agent"] = ev.agent_key
        state["last_result"] = result
        state["completed_agents"] = list(dict.fromkeys(state.get("completed_agents", []) + [ev.agent_key]))
        state["previous_agent_outputs"] = state.get("previous_agent_outputs", [])
        state["previous_agent_outputs"].append({"agent": ev.agent_key, "result": result})
        state["status"] = "completed"
        state["last_action"] = "workflow_completed"
        await ctx.store.set("workflow_state", state)

        return StopEvent(
            result={
                "agent": ev.agent_key,
                "reply": result.get("reply", ""),
                "products": result.get("products", []),
                "workflow_state": state,
                "ok": result.get("ok", True),
                "error": result.get("error"),
            }
        )
