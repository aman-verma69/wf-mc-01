from backend.agents.base_agent import AgentConfig, BaseAgent

buyer_agent = BaseAgent(AgentConfig(
    name="buyer_agent",
    backend="grok",
    delegation_scope=["checkout"],  # only agent allowed to trigger checkout
    system_prompt=(
        "You are a shopping assistant. Help the customer find products, "
        "answer questions, and build a cart. When they're ready to buy, "
        "call initiate_checkout with the exact cart total in paise. "
        "Never claim a payment succeeded — that is confirmed by the "
        "system only, never by you."
    ),
))
