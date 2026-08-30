from backend.workflows.intent import classify_intent, extract_price_ceiling_paise


def test_buyer_search_intent():
    assert classify_intent("buyer", "show me earbuds under 4000") == "search_catalog"
    assert classify_intent("buyer", "recommend a good t-shirt") == "search_catalog"


def test_buyer_checkout_intent():
    assert classify_intent("buyer", "I'll take the earbuds, buy it") == "initiate_checkout"


def test_buyer_general_intent():
    assert classify_intent("buyer", "hi there") == "general"


def test_customer_order_status_intent():
    assert classify_intent("customer", "where is my order") == "order_status"
    assert classify_intent("customer", "what's the weather like") == "general"


def test_price_ceiling_extraction():
    assert extract_price_ceiling_paise("show me earbuds under 4000") == 400000
    assert extract_price_ceiling_paise("anything below rs. 1,200") == 120000
    assert extract_price_ceiling_paise("no price mentioned here") is None
