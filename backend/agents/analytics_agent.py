from backend.agents.base_agent import AgentConfig, BaseAgent

analytics_agent = BaseAgent(AgentConfig(
    name="analytics_agent",
    backend="gpt-oss",
    delegation_scope=[],
    system_prompt=(
        "You interpret and narrate business metrics for a human reader. "
        "You do NOT compute numbers yourself — always request pre-computed "
        "figures from the analytics data service and explain what they mean. "
        "Never invent or estimate a number that wasn't provided to you."
    ),
))
