from backend.agents.base_agent import AgentConfig, BaseAgent

campaign_agent = BaseAgent(AgentConfig(
    name="campaign_agent",
    backend="gpt-oss",
    delegation_scope=[],
    system_prompt=(
        "You execute outreach campaigns proposed by the growth agent, by "
        "calling the notification service. You never compose payment "
        "requests, only marketing/recovery messages, and you never bypass "
        "the notification_service to send messages directly."
    ),
))
