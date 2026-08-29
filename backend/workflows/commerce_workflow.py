"""
LlamaIndex Workflow orchestrator. Routes an incoming message to the right
agent, then lets that agent's own tool-calling loop (base_agent.py) handle
the rest. This file only does ROUTING — no payment logic, no policy checks.

Requires: pip install llama-index-core
"""
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.analytics_agent import analytics_agent
from backend.agents.buyer_agent import buyer_agent
from backend.agents.campaign_agent import campaign_agent
from backend.agents.catalog_agent import catalog_agent
from backend.agents.customer_agent import customer_agent
from backend.agents.growth_agent import growth_agent

AGENTS = {
    "buyer": buyer_agent,
    "catalog": catalog_agent,
    "customer": customer_agent,
    "analytics": analytics_agent,
    "growth": growth_agent,
    "campaign": campaign_agent,
}


class RouteEvent(Event):
    agent_key: str
    message: str


class CommerceWorkflow(Workflow):
    """Usage:
        wf = CommerceWorkflow(timeout=60)
        result = await wf.run(db=db, message=user_message, agent_key="buyer")
    """

    @step
    async def route(self, ctx: Context, ev: StartEvent) -> RouteEvent:
        agent_key = ev.get("agent_key", "buyer")
        if agent_key not in AGENTS:
            raise ValueError(f"Unknown agent_key: {agent_key}. Valid: {list(AGENTS)}")
        await ctx.store.set("db", ev.get("db"))
        return RouteEvent(agent_key=agent_key, message=ev.get("message"))

    @step
    async def dispatch(self, ctx: Context, ev: RouteEvent) -> StopEvent:
        db: AsyncSession = await ctx.store.get("db")
        agent = AGENTS[ev.agent_key]
        reply = await agent.run(db, ev.message)
        return StopEvent(result={"agent": ev.agent_key, "reply": reply})
