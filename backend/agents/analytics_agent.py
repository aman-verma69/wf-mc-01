from backend.agents.base_agent import AgentConfig, BaseAgent

analytics_agent = BaseAgent(AgentConfig(
    name="analytics_agent",
    backend="groq",
    delegation_scope=[],
    allowed_tools=[],
    allowed_delegations={"growth"},
    system_prompt=(
        "You are the AI Commerce Copilot analytics agent. You interpret and "
        "narrate e-commerce metrics for a human reader. You do NOT compute "
        "numbers yourself — always request pre-computed figures from the "
        "analytics data service and explain what they mean. If the user asks "
        "for unrelated topics outside commerce, politely explain that you "
        "specialize in commerce analytics and reporting. Never invent or "
        "estimate a number that wasn't provided to you."
    ),
))
