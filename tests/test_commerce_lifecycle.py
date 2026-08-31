from backend.policy.guardrail import CheckoutRequest, GateDecision, _check_spend_limit
from backend.services.cart_service import (
    add_item_to_cart,
    calculate_cart_total_paise,
    convert_product_to_cart_item,
    normalize_cart,
    remove_item_from_cart,
    update_cart_item_quantity,
)


def test_product_to_cart_conversion_uses_trusted_price_from_catalog():
    product = {
        "id": "sku_101",
        "name": "Sony WH-CH520",
        "price": 3990,
        "currency": "INR",
        "source": "catalog",
    }

    item = convert_product_to_cart_item(product, quantity=2)

    assert item["product_id"] == "sku_101"
    assert item["name"] == "Sony WH-CH520"
    assert item["quantity"] == 2
    assert item["unit_price_paise"] == 3990
    assert item["currency"] == "INR"


def test_cart_lifecycle_updates_total_and_quantities():
    cart = normalize_cart({"customer_id": "cust-42", "items": []})
    cart = add_item_to_cart(cart, convert_product_to_cart_item({"id": "sku_1", "name": "Earbuds", "price": 2990, "currency": "INR"}, quantity=1))
    cart = add_item_to_cart(cart, convert_product_to_cart_item({"id": "sku_2", "name": "Case", "price": 590, "currency": "INR"}, quantity=2))

    assert calculate_cart_total_paise(cart) == 4170
    cart = update_cart_item_quantity(cart, "sku_1", 3)
    assert calculate_cart_total_paise(cart) == 10150
    cart = remove_item_from_cart(cart, "sku_2")
    assert calculate_cart_total_paise(cart) == 8970


def test_checkout_amount_is_rebuilt_from_cart_not_llm_input():
    cart = normalize_cart({
        "customer_id": "cust-42",
        "items": [
            {"product_id": "sku_1", "name": "Earbuds", "quantity": 1, "unit_price_paise": 2990, "currency": "INR"},
            {"product_id": "sku_2", "name": "Case", "quantity": 2, "unit_price_paise": 590, "currency": "INR"},
        ],
    })

    assert calculate_cart_total_paise(cart) == 4170


def test_guardrail_escalates_when_amount_exceeds_autonomous_limit(monkeypatch):
    monkeypatch.setattr("backend.policy.guardrail.settings.MAX_AUTONOMOUS_SPEND_PAISE", 500000)
    monkeypatch.setattr("backend.policy.guardrail.settings.REQUIRE_HUMAN_CONFIRMATION_ABOVE_LIMIT", True)

    req = CheckoutRequest(actor="buyer_agent", customer_id="cust-42", amount_paise=600000, delegation_scope=["checkout"])
    result = _check_spend_limit(req)

    assert result is not None
    assert result.decision == GateDecision.ESCALATED
    assert "human confirmation" in result.reason.lower()
