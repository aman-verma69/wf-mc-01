from backend.agents.base_agent import AgentConfig, BaseAgent

growth_agent = BaseAgent(AgentConfig(
    name="growth_agent",
    backend="groq",
    delegation_scope=[],
    system_prompt=(
        "You identify growth opportunities: abandoned carts worth recovering, "
        "market trends worth acting on, pricing gaps versus competitors. "
        "You propose actions for the campaign_agent to execute — you do "
        "not send messages yourself and you never touch payments."
    ),
))
