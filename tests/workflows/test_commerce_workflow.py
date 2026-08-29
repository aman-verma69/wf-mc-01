import pytest

from backend.workflows.commerce_workflow import AGENTS


def test_all_agents_registered():
    expected = {"buyer", "catalog", "customer", "analytics", "growth", "campaign"}
    assert set(AGENTS.keys()) == expected


def test_all_agents_use_gpt_oss_backend():
    for key, agent in AGENTS.items():
        assert agent.config.backend == "gpt-oss", f"{key} is not on gpt-oss backend"
