import pytest

from backend.policy.guardrail import CheckoutRequest, GateDecision, _check_delegation_scope, _check_spend_limit


def test_blocks_agent_without_checkout_scope():
    req = CheckoutRequest(actor="catalog_agent", customer_id="c1", amount_paise=1000, delegation_scope=[])
    result = _check_delegation_scope(req)
    assert result is not None
    assert result.decision == GateDecision.BLOCKED


def test_allows_agent_with_checkout_scope():
    req = CheckoutRequest(actor="buyer_agent", customer_id="c1", amount_paise=1000, delegation_scope=["checkout"])
    result = _check_delegation_scope(req)
    assert result is None  # no block = passes this check


def test_escalates_over_spend_limit(monkeypatch):
    from backend.policy import guardrail
    monkeypatch.setattr(guardrail.settings, "MAX_AUTONOMOUS_SPEND_PAISE", 100000)
    monkeypatch.setattr(guardrail.settings, "REQUIRE_HUMAN_CONFIRMATION_ABOVE_LIMIT", True)

    req = CheckoutRequest(actor="buyer_agent", customer_id="c1", amount_paise=200000)
    result = _check_spend_limit(req)
    assert result is not None
    assert result.decision == GateDecision.ESCALATED


def test_allows_under_spend_limit(monkeypatch):
    from backend.policy import guardrail
    monkeypatch.setattr(guardrail.settings, "MAX_AUTONOMOUS_SPEND_PAISE", 500000)

    req = CheckoutRequest(actor="buyer_agent", customer_id="c1", amount_paise=1000)
    result = _check_spend_limit(req)
    assert result is None
