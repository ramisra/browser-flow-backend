import pytest

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from app.core.agents.reasoning_engine import ReasoningEngine


@pytest.mark.asyncio
async def test_reasoning_engine_iterates_query(monkeypatch):
    async def fake_query(*args, **kwargs):
        yield AssistantMessage(content=[TextBlock(text="partial")], model="test")
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session",
            total_cost_usd=None,
            usage={"input_tokens": 1},
            result="final-response",
            structured_output=None,
        )

    monkeypatch.setattr(
        "app.core.agents.reasoning_engine.query", fake_query
    )

    engine = ReasoningEngine()
    result = await engine.reason("hello", context=None)

    assert result["result"] == "final-response"
    assert result["metadata"]["usage"] == {"input_tokens": 1}


@pytest.mark.asyncio
async def test_reasoning_engine_uses_mcp_client(monkeypatch):
    class FakeClient:
        def __init__(self, options=None):
            self.options = options
            self.prompt = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def query(self, prompt):
            self.prompt = prompt

        async def receive_response(self):
            yield AssistantMessage(
                content=[TextBlock(text="intermediate")],
                model="test",
            )
            yield ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="session",
                total_cost_usd=None,
                usage={"output_tokens": 2},
                result="mcp-final",
                structured_output=None,
            )

    monkeypatch.setattr(
        "app.core.agents.reasoning_engine.ClaudeSDKClient",
        FakeClient,
    )

    engine = ReasoningEngine()
    result = await engine.reason(
        "hello",
        context=None,
        tools=["mcp__excel__excel_write"],
        mcp_servers={"excel": {"type": "sdk", "name": "excel", "instance": object()}},
    )

    assert result["result"] == "mcp-final"
    assert result["metadata"]["usage"] == {"output_tokens": 2}
