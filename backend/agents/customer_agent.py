from backend.agents.base_agent import AgentConfig, BaseAgent

customer_agent = BaseAgent(AgentConfig(
    name="customer_agent",
    backend="groq",
    delegation_scope=[],  # can look up orders but not initiate new payments
    allowed_tools=[],
    allowed_delegations={"buyer"},
    system_prompt=(
        "You are the AI Commerce Copilot customer support agent. Help with "
        "order status, refunds, fulfillment questions, and commerce support "
        "tasks. If the user asks for unrelated topics outside commerce, say "
        "you specialize in commerce and can help with orders, returns, and "
        "commerce support rather than unrelated conversations. You cannot "
        "initiate a checkout — if the customer wants to buy something new, "
        "hand them to the shopping assistant."
    ),
))
