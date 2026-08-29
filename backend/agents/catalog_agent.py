from backend.agents.base_agent import AgentConfig, BaseAgent

catalog_agent = BaseAgent(AgentConfig(
    name="catalog_agent",
    backend="groq",
    delegation_scope=[],  # no checkout access — read-only research
    system_prompt=(
        "You research products, prices, and competitor listings using "
        "web search. You never initiate payments or checkouts."
    ),
))
