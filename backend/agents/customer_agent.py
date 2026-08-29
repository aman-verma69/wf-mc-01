from backend.agents.base_agent import AgentConfig, BaseAgent

customer_agent = BaseAgent(AgentConfig(
    name="customer_agent",
    backend="groq",
    delegation_scope=[],  # can look up orders but not initiate new payments
    system_prompt=(
        "You are a customer support agent. Help with order status, refund "
        "requests, and general questions. You cannot initiate a checkout — "
        "if the customer wants to buy something new, hand them to the "
        "shopping assistant."
    ),
))
