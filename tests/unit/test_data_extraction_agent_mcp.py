import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.data_extraction_agent import DataExtractionAgent
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.tool_integration import ToolIntegration
from app.core.agents.evaluator import Evaluator
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.tool_registry import ToolRegistry


@pytest.mark.asyncio
async def test_data_extraction_agent_uses_mcp_path():
    prompt_manager = PromptManager()
    tool_registry = ToolRegistry()
    tool_integration = ToolIntegration(tool_registry)
    evaluator = Evaluator()

    excel_tools = MagicMock()
    excel_tools.create_excel_file = AsyncMock()

    reasoning_engine = MagicMock(spec=ReasoningEngine)
    reasoning_engine.reason = AsyncMock(
        return_value={
            "result": (
                '[{"name": "Jane Doe", "designation": "CTO"}]\n'
                '{"file_path": "app/storage/excel/data_test.xlsx"}'
            ),
            "metadata": {},
        }
    )

    agent = DataExtractionAgent(
        agent_id="test_agent",
        prompt_manager=prompt_manager,
        tool_integration=tool_integration,
        evaluator=evaluator,
        reasoning_engine=reasoning_engine,
        excel_tools=excel_tools,
        mcp_servers={"excel": {"type": "sdk", "name": "excel", "instance": object()}},
        allowed_tools=["mcp__excel__excel_write"],
    )

    result = await agent.execute(
        {
            "selected_text": "Jane Doe, CTO",
            "user_context": "Extract name and designation",
        }
    )

    assert result.status == "completed"
    assert result.excel_file_path == "app/storage/excel/data_test.xlsx"
    excel_tools.create_excel_file.assert_not_awaited()
