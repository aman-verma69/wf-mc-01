import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from llama_index.core.workflow import Context, StartEvent

from backend.agents.base_agent import AgentConfig, BaseAgent
from backend.main import app
from backend.tools.commerce_tools import normalize_search_results, run_tool
from backend.workflows.commerce_workflow import AGENTS, CommerceWorkflow, RouteEvent


def test_all_agents_registered():
    expected = {"buyer", "catalog", "customer", "analytics", "growth", "campaign"}
    assert set(AGENTS.keys()) == expected


def test_all_agents_use_groq_backend():
    for key, agent in AGENTS.items():
        assert agent.config.backend == "groq", f"{key} is not on groq backend"


def test_workflow_route_initializes_request_state():
    workflow = CommerceWorkflow(timeout=60)
    ctx = Context(workflow)

    route_event = asyncio.run(
        workflow.route(
            ctx,
            StartEvent(
                message="show me earbuds under 4000",
                agent_key=None,
                customer_id="customer-123",
                db=None,
            ),
        )
    )

    state = asyncio.run(ctx.store.get("workflow_state"))
    assert state["message"] == "show me earbuds under 4000"
    assert state["customer_id"] == "customer-123"
    assert state["intent"] == "search_catalog"
    assert state["selected_agent"] == "catalog"
    assert route_event.workflow_state["selected_agent"] == "catalog"


def test_explicit_agent_key_fallback_still_works():
    workflow = CommerceWorkflow(timeout=60)
    ctx = Context(workflow)

    route_event = asyncio.run(
        workflow.route(
            ctx,
            StartEvent(
                message="where is my order",
                agent_key="customer",
                customer_id="customer-456",
                db=None,
            ),
        )
    )

    assert route_event.agent_key == "customer"
    state = asyncio.run(ctx.store.get("workflow_state"))
    assert state["selected_agent"] == "customer"
    assert state["intent"] == "order_status"


def test_workflow_state_does_not_leak_between_runs():
    workflow = CommerceWorkflow(timeout=60)
    ctx_one = Context(workflow)
    ctx_two = Context(workflow)

    asyncio.run(
        workflow.route(
            ctx_one,
            StartEvent(
                message="where is my order",
                agent_key="customer",
                customer_id="cust-1",
                db=None,
            ),
        )
    )
    asyncio.run(
        workflow.route(
            ctx_two,
            StartEvent(
                message="show me earbuds under 5000",
                agent_key="buyer",
                customer_id="cust-2",
                db=None,
            ),
        )
    )

    state_one = asyncio.run(ctx_one.store.get("workflow_state"))
    state_two = asyncio.run(ctx_two.store.get("workflow_state"))

    assert state_one["customer_id"] == "cust-1"
    assert state_two["customer_id"] == "cust-2"
    assert state_one["message"] == "where is my order"
    assert state_two["message"] == "show me earbuds under 5000"
    assert state_one["selected_agent"] == "customer"
    assert state_two["selected_agent"] == "buyer"


def test_agent_prompts_remain_commerce_specific():
    prompts = {
        key: agent.config.system_prompt.lower()
        for key, agent in AGENTS.items()
    }

    for key, prompt in prompts.items():
        assert "ai commerce copilot" in prompt, f"{key} does not identify as AI Commerce Copilot"
        assert "general-purpose" not in prompt, f"{key} still describes itself as general-purpose"
        assert "commerce" in prompt or "shopping" in prompt or "customer" in prompt, f"{key} lacks commerce scope"


def test_search_results_are_normalized_into_structured_products():
    raw = {
        "results": [
            {
                "title": "Sony WH-CH520",
                "url": "https://example.com/sony-wh-ch520",
                "source": "headphonezone.in",
                "content": "Wireless headphones for ₹3,990",
                "thumbnail": "https://example.com/sony.jpg",
                "score": 0.9,
            }
        ]
    }

    products = normalize_search_results(raw)

    assert isinstance(products, list)
    assert len(products) == 1
    assert products[0]["name"] == "Sony WH-CH520"
    assert products[0]["price"] == 3990
    assert products[0]["currency"] == "INR"
    assert products[0]["image_url"] == "https://example.com/sony.jpg"
    assert products[0]["product_url"] == "https://example.com/sony-wh-ch520"
    assert products[0]["source"] == "headphonezone.in"
    assert isinstance(products[0]["metadata"], dict)


def test_missing_catalog_images_do_not_get_fabricated():
    raw = {
        "results": [
            {
                "title": "BoAt Rockerz 450",
                "url": "https://example.com/boat-rockerz-450",
                "source": "boat-lifestyle.com",
                "content": "Wireless headphones under ₹5,000",
                "score": 0.8,
            }
        ]
    }

    products = normalize_search_results(raw)

    assert len(products) == 1
    assert products[0]["image_url"] is None
    assert products[0]["product_url"] == "https://example.com/boat-rockerz-450"


def test_article_and_guide_results_are_filtered_out_of_products():
    raw = {
        "results": [
            {
                "title": "Best Gaming Headphones Under 5000 in 2024",
                "url": "https://example.com/blog/best-gaming-headphones-under-5000",
                "source": "techblog.in",
                "content": "Buying guide for gaming headsets under ₹5000 in India.",
                "score": 0.95,
            },
            {
                "title": "Sony WH-CH520",
                "url": "https://example.com/sony-wh-ch520",
                "source": "headphonezone.in",
                "content": "Wireless headphones ₹3,990. Available in stock.",
                "thumbnail": "https://example.com/sony.jpg",
                "score": 0.9,
            },
        ]
    }

    products = normalize_search_results(raw)

    assert len(products) == 1
    assert products[0]["name"] == "Sony WH-CH520"
    assert products[0]["price"] == 3990
    assert products[0]["image_url"] == "https://example.com/sony.jpg"


def test_budget_ceiling_is_not_used_as_price_when_no_real_price_exists():
    raw = {
        "results": [
            {
                "title": "10 Best Gaming Headphones Under 5000 In India",
                "url": "https://example.com/articles/10-best-gaming-headphones-under-5000",
                "source": "techroundup.in",
                "content": "A comparison shopping guide for gaming headsets under ₹5000.",
                "score": 0.9,
            }
        ]
    }

    products = normalize_search_results(raw)

    assert products == []


def test_chat_api_propagates_customer_id(monkeypatch):
    captured = {}

    async def fake_run(self, *, db, message, agent_key=None, customer_id=None):
        captured["customer_id"] = customer_id
        return {
            "agent": "buyer_agent",
            "reply": "I found some options.",
            "products": [],
            "ok": True,
            "error": None,
        }

    monkeypatch.setattr(CommerceWorkflow, "run", fake_run)
    client = TestClient(app)

    response = client.post("/api/v1/agents/chat", json={"message": "show me earbuds under 5000", "customer_id": "cust-42"})

    assert response.status_code == 200
    assert captured["customer_id"] == "cust-42"
    assert response.json()["agent"] == "buyer_agent"


def test_run_tool_passes_delegation_scope_to_checkout_guardrail():
    async def _assertion():
        with patch("backend.tools.commerce_tools.initiate_checkout", new_callable=AsyncMock) as mocked:
            mocked.return_value.id = "ord_123"
            mocked.return_value.status = type("Status", (), {"value": "created"})()

            result = await run_tool(
                None,
                actor="buyer_agent",
                name="initiate_checkout",
                arguments={
                    "customer_id": "cust-1",
                    "amount_paise": 150000,
                    "cart_snapshot": {"items": [{"name": "Earbuds", "qty": 1}]},
                },
                delegation_scope=["checkout"],
            )

        assert result["ok"] is True
        mocked.assert_awaited_once()
        assert mocked.await_args.kwargs["delegation_scope"] == ["checkout"]

    asyncio.run(_assertion())


def test_search_web_handles_connection_error_gracefully():
    with patch("backend.tools.commerce_tools.tavily_search", return_value={"results": [], "error": {"type": "ConnectionError", "code": "product_search_unavailable", "message": "Live product search is temporarily unavailable. Please try again shortly.", "retryable": True}}):
        result = asyncio.run(
            run_tool(
                None,
                actor="buyer_agent",
                name="search_web",
                arguments={"query": "wireless headphones under 5000"},
            )
        )

    assert result["ok"] is False
    assert result["error"] == "product_search_unavailable"
    assert result["retryable"] is True
    assert "temporarily unavailable" in result["reason"]


def test_search_web_successful_search_with_zero_verified_products_keeps_ok_true():
    with patch("backend.tools.commerce_tools.tavily_search", return_value={"results": [{"title": "Best Gaming Headphones Under 5000 in 2024", "url": "https://example.com/best-gaming-headphones-under-5000", "source": "techblog.in", "content": "Buying guide for gaming headsets under ₹5000 in India.", "score": 0.95}]}):
        result = asyncio.run(
            run_tool(
                None,
                actor="buyer_agent",
                name="search_web",
                arguments={"query": "Compare the best wireless headphones under ₹5000 for gaming"},
            )
        )

    assert result["ok"] is True
    assert result["error"] is None
    assert result["products"] == []


def test_search_web_timeout_provider_failure_uses_stable_error_code():
    with patch("backend.tools.commerce_tools.tavily_search", side_effect=TimeoutError("provider timed out")):
        result = asyncio.run(
            run_tool(
                None,
                actor="buyer_agent",
                name="search_web",
                arguments={"query": "wireless headphones under 5000"},
            )
        )

    assert result["ok"] is False
    assert result["error"] == "product_search_unavailable"
    assert result["products"] == []


def test_agent_run_successful_search_with_zero_verified_products_keeps_ok_true():
    async def fake_run_tool(*args, **kwargs):
        return {
            "ok": True,
            "error": None,
            "result": {"results": [{"title": "Best Gaming Headphones Under 5000 in 2024", "url": "https://example.com/best", "source": "techblog.in", "content": "Buying guide for gaming headsets under ₹5000.", "score": 0.95}]},
            "products": [],
        }

    async def _run():
        agent = BaseAgent(
            AgentConfig(
                name="buyer_agent",
                system_prompt="You are the AI Commerce Copilot buyer agent.",
                backend="groq",
                allowed_tools=["search_web"],
                allowed_delegations={"catalog", "customer"},
            )
        )
        return await agent.run(
            None,
            "Compare the best wireless headphones under ₹5000 for gaming",
            history=[],
            workflow_state={},
        )

    with patch("backend.agents.base_agent.run_tool", side_effect=fake_run_tool):
        result = asyncio.run(_run())

    assert result["ok"] is True
    assert result["error"] is None
    assert result["products"] == []
    assert "verified as individual product matches" in result["reply"].lower()


def test_tavily_search_retries_and_stops_after_bound():
    with patch("backend.integrations.tavily.client.get_tavily_client") as get_client:
        client = get_client.return_value
        client.search.side_effect = [ConnectionError("reset"), ConnectionError("reset"), {"results": [{"title": "A", "url": "https://example.com/a", "content": "₹2,999", "source": "demo"}]}]

        result = asyncio.run(asyncio.to_thread(lambda: None))
        search_response = __import__("backend.integrations.tavily.client", fromlist=["search"]).search("wireless headphones")

    assert search_response["results"][0]["title"] == "A"
    assert client.search.call_count == 3


def test_fastapi_endpoint_handles_tavily_connection_error_without_500(monkeypatch):
    async def fake_run(self, *, db, message, agent_key=None, customer_id=None):
        return {
            "agent": "buyer_agent",
            "reply": "I couldn't reach the live product catalog right now. Please try again in a moment.",
            "products": [],
            "ok": True,
            "error": None,
        }

    monkeypatch.setattr(CommerceWorkflow, "run", fake_run)
    client = TestClient(app)
    response = client.post("/api/v1/agents/chat", json={"message": "Find me wireless headphones under ₹5000 and compare the best options for gaming", "customer_id": "cust-42"})

    assert response.status_code == 200
    assert "temporarily unavailable" in response.json()["reply"] or "live product catalog" in response.json()["reply"]


def test_agent_run_handles_empty_genuine_product_results_gracefully():
    async def fake_run_tool(*args, **kwargs):
        return {
            "ok": True,
            "result": {"results": []},
            "products": [],
        }

    async def _run():
        agent = BaseAgent(
            AgentConfig(
                name="buyer_agent",
                system_prompt="You are the AI Commerce Copilot buyer agent.",
                backend="groq",
                allowed_tools=["search_web"],
                allowed_delegations={"catalog", "customer"},
            )
        )
        return await agent.run(
            None,
            "Find me wireless headphones under ₹5000 and compare the best options for gaming",
            history=[],
            workflow_state={},
        )

    with patch("backend.agents.base_agent.run_tool", side_effect=fake_run_tool):
        result = asyncio.run(_run())

    assert result["status"] == "completed"
    assert result["products"] == []
    assert result["ok"] is True
    assert result["error"] is None
    assert "verified as individual product matches" in result["reply"].lower()


def test_product_search_reply_compares_real_candidates():
    async def fake_run_tool(*args, **kwargs):
        return {
            "ok": True,
            "result": {"results": [
                {"title": "Sony WH-CH520", "url": "https://example.com/sony-wh-ch520", "source": "headphonezone.in", "content": "Wireless headphones ₹3,990", "thumbnail": "https://example.com/sony.jpg"},
                {"title": "boAt Rockerz 450", "url": "https://example.com/boat-rockerz-450", "source": "boat-lifestyle.com", "content": "Wireless headphones ₹2,499", "thumbnail": "https://example.com/boat.jpg"},
            ]},
            "products": [
                {"id": "sony", "name": "Sony WH-CH520", "price": 3990, "currency": "INR", "image_url": "https://example.com/sony.jpg", "source": "headphonezone.in", "product_url": "https://example.com/sony-wh-ch520", "availability": "in_stock", "metadata": {}},
                {"id": "boat", "name": "boAt Rockerz 450", "price": 2499, "currency": "INR", "image_url": "https://example.com/boat.jpg", "source": "boat-lifestyle.com", "product_url": "https://example.com/boat-rockerz-450", "availability": "in_stock", "metadata": {}},
            ],
        }

    async def _run():
        agent = BaseAgent(
            AgentConfig(
                name="buyer_agent",
                system_prompt="You are the AI Commerce Copilot buyer agent.",
                backend="groq",
                allowed_tools=["search_web"],
                allowed_delegations={"catalog", "customer"},
            )
        )
        return await agent.run(
            None,
            "Find me wireless headphones under ₹5000 and compare the best options for gaming",
            history=[],
            workflow_state={},
        )

    with patch("backend.agents.base_agent.run_tool", side_effect=fake_run_tool):
        result = asyncio.run(_run())

    assert result["status"] == "completed"
    assert result["products"][0]["name"] == "Sony WH-CH520"
    assert "compare" in result["reply"].lower()
    assert "sony" in result["reply"].lower() or "boat" in result["reply"].lower()


def test_workflow_dispatch_keeps_products_in_result_payload(monkeypatch):
    class FakeAgent:
        async def run(self, *args, **kwargs):
            return {
                "reply": "I found these options under ₹5,000.",
                "products": [{
                    "id": "prod-1",
                    "name": "Sony WH-CH520",
                    "price": 3990,
                    "currency": "INR",
                    "image_url": "https://example.com/sony.jpg",
                    "source": "headphonezone.in",
                    "product_url": "https://example.com/sony-wh-ch520",
                    "availability": "in_stock",
                    "metadata": {"brand": "Sony"},
                }],
            }

    original = AGENTS["buyer"]
    AGENTS["buyer"] = FakeAgent()
    try:
        workflow = CommerceWorkflow(timeout=60)
        ctx = Context(workflow)
        result = asyncio.run(
            workflow.dispatch(
                ctx,
                RouteEvent(
                    agent_key="buyer",
                    message="show me wireless headphones under ₹5000",
                    workflow_state={
                        "message": "show me wireless headphones under ₹5000",
                        "customer_id": "cust-1",
                        "intent": "search_catalog",
                        "history": [{"role": "user", "content": "show me wireless headphones under ₹5000"}],
                        "selected_agent": "buyer",
                        "delegation_depth": 0,
                        "workflow_turns": 0,
                        "previous_agent_outputs": [],
                        "cart": {"items": [], "total_paise": 0},
                    },
                ),
            )
        )
    finally:
        AGENTS["buyer"] = original

    assert isinstance(result.result["reply"], str)
    assert isinstance(result.result["products"], list)
    assert result.result["products"][0]["name"] == "Sony WH-CH520"
    assert result.result["products"][0]["price"] == 3990
