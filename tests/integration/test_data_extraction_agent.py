"""Integration tests for DataExtractionAgent."""

import pytest
from pathlib import Path
import pandas as pd
from unittest.mock import AsyncMock, MagicMock

from app.agents.data_extraction_agent import DataExtractionAgent
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.tool_integration import ToolIntegration
from app.core.agents.evaluator import Evaluator
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.tool_registry import ToolRegistry
from app.core.tools.excel_tools import ExcelTools
from app.core.agents.agent_context import AgentContext
from app.models.task_identification import TaskIdentificationResult
from app.core.task_types import TaskType


@pytest.fixture
def mock_reasoning_engine():
    """Mock reasoning engine."""
    engine = MagicMock(spec=ReasoningEngine)
    engine.reason = AsyncMock(return_value={
        "result": '[{"name": "Ratikesh Misra", "designation": "VP engineering", "company": "Flobiz", "total_connection": 140}]',
        "metadata": {},
    })
    return engine


@pytest.fixture
def data_extraction_agent(temp_storage_dir, mock_reasoning_engine):
    """Create DataExtractionAgent instance for testing."""
    prompt_manager = PromptManager()
    tool_registry = ToolRegistry()
    tool_integration = ToolIntegration(tool_registry)
    evaluator = Evaluator()
    excel_tools = ExcelTools(storage_dir=str(temp_storage_dir))

    agent = DataExtractionAgent(
        agent_id="test_data_extraction_agent",
        prompt_manager=prompt_manager,
        tool_integration=tool_integration,
        evaluator=evaluator,
        reasoning_engine=mock_reasoning_engine,
        excel_tools=excel_tools,
    )

    return agent


@pytest.mark.asyncio
async def test_extract_simple_tabular_data(data_extraction_agent, sample_extraction_data):
    """Test extraction of simple tabular data."""
    task_input = {
        "selected_text": "Product A: $100, Stock: 50\nProduct B: $200, Stock: 30",
        "user_context": "Extract product data with name, price, and stock",
    }

    result = await data_extraction_agent.execute(task_input)

    assert result.status == "completed"
    assert result.excel_file_path is not None
    assert Path(result.excel_file_path).exists()
    assert result.extracted_data is not None


@pytest.mark.asyncio
async def test_extract_lead_tracking_data(
    data_extraction_agent, sample_selected_text, sample_user_context
):
    """Test extraction of lead tracking data."""
    task_input = {
        "selected_text": sample_selected_text,
        "user_context": sample_user_context,
    }

    result = await data_extraction_agent.execute(task_input)

    assert result.status == "completed"
    assert result.excel_file_path is not None
    assert Path(result.excel_file_path).exists()

    # Validate Excel file
    df = pd.read_excel(result.excel_file_path, engine="openpyxl")
    assert len(df) > 0

    # Check that columns match user_context requirements
    columns_lower = [col.lower() for col in df.columns]
    assert "name" in columns_lower or any("name" in col.lower() for col in df.columns)
    assert "designation" in columns_lower or any("designation" in col.lower() for col in df.columns)


@pytest.mark.asyncio
async def test_extract_with_missing_fields(data_extraction_agent):
    """Test handling of missing fields in input."""
    task_input = {
        "selected_text": "Ratikesh Misra, VP engineering",
        "user_context": "Extract name, designation, company",
    }

    result = await data_extraction_agent.execute(task_input)

    assert result.status == "completed"
    assert result.excel_file_path is not None

    # Should still create Excel with available data
    df = pd.read_excel(result.excel_file_path, engine="openpyxl")
    assert len(df) > 0


@pytest.mark.asyncio
async def test_extract_with_only_user_context(data_extraction_agent):
    """Test extraction with only user_context (no selected_text)."""
    task_input = {
        "user_context": "Extract product data: iPhone 15 - $999 - 50 units, Samsung S24 - $899 - 30 units",
    }

    result = await data_extraction_agent.execute(task_input)

    assert result.status == "completed"
    assert result.excel_file_path is not None


@pytest.mark.asyncio
async def test_extract_with_only_selected_text(data_extraction_agent):
    """Test extraction with only selected_text (no user_context)."""
    task_input = {
        "selected_text": "Product A: $100, Product B: $200",
    }

    result = await data_extraction_agent.execute(task_input)

    assert result.status == "completed"
    assert result.excel_file_path is not None
