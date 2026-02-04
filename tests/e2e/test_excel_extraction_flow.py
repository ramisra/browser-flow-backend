"""End-to-end tests for complete Excel extraction flow."""

import pytest
from pathlib import Path
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.agent_registry import AgentRegistry
from app.core.tool_registry import ToolRegistry
from app.core.tools.excel_tools import ExcelTools
from app.services.embedding import EmbeddingService
from app.services.semantic_knowledge_service import SemanticKnowledgeService
from app.services.task_orchestrator import TaskOrchestrator
from app.core.agents.agent_spawner import AgentSpawner
from app.models.task_identification import TaskIdentificationResult
from app.core.task_types import TaskType
from app.core.agents.agent_context import AgentContext


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    return service


@pytest.fixture
def mock_context_repository():
    """Mock context repository."""
    repo = MagicMock()
    repo.search_similar_contexts = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def task_orchestrator_setup(temp_storage_dir, mock_embedding_service, mock_context_repository):
    """Set up task orchestrator with mocked dependencies."""
    agent_registry = AgentRegistry()
    tool_registry = ToolRegistry()
    
    semantic_knowledge_service = SemanticKnowledgeService(
        embedding_service=mock_embedding_service,
        context_repository=mock_context_repository,
    )
    
    excel_tools = ExcelTools(storage_dir=str(temp_storage_dir))
    agent_spawner = AgentSpawner(
        tool_registry=tool_registry,
        embedding_service=mock_embedding_service,
        semantic_knowledge_service=semantic_knowledge_service,
        excel_tools=excel_tools,
    )
    
    task_orchestrator = TaskOrchestrator(
        agent_registry=agent_registry,
        agent_spawner=agent_spawner,
    )
    
    return task_orchestrator


@pytest.mark.asyncio
async def test_e2e_lead_tracking_extraction(task_orchestrator_setup):
    """End-to-end test: Extract lead data from selected_text with user_context."""
    task_orchestrator = task_orchestrator_setup
    
    # Create task identification result
    task_identification = TaskIdentificationResult(
        task_type=TaskType.EXTRACT_DATA_TO_SHEET,
        confidence=0.9,
        reasoning="User wants to extract lead data to Excel",
        input={},
        output={},
    )
    
    # Prepare task input
    task_input = {
        "selected_text": "140 connection, Ratikesh Misra, VP engineering Flobiz, CTO furrl",
        "user_context": "Create the excel sheet for tracking lead with name, designation and total connection",
    }
    
    # Mock reasoning engine for the agent
    with patch('app.agents.data_extraction_agent.ReasoningEngine') as mock_reasoning_class:
        mock_reasoning = MagicMock()
        mock_reasoning.reason = AsyncMock(return_value={
            "result": '[{"name": "Ratikesh Misra", "designation": "VP engineering", "company": "Flobiz", "total_connection": 140}, {"name": "Unknown", "designation": "CTO", "company": "furrl", "total_connection": null}]',
            "metadata": {},
        })
        mock_reasoning_class.return_value = mock_reasoning
        
        # Execute orchestration
        result = await task_orchestrator.orchestrate_task(
            task_identification=task_identification,
            user_context=task_input["user_context"],
            context_metadata={},
            context_result=None,
            task_input=task_input,
        )
    
    # Validate result
    assert result.status == "completed"
    assert "result" in result.result or result.result.get("excel_file_path")
    
    # Check if Excel file was created
    excel_path = None
    if isinstance(result.result, dict):
        excel_path = result.result.get("excel_file_path")
        if not excel_path and "result" in result.result:
            excel_path = result.result["result"].get("excel_file_path")
    
    if excel_path:
        assert Path(excel_path).exists()
        
        # Read and validate Excel content
        df = pd.read_excel(excel_path, engine="openpyxl")
        assert len(df) > 0
        
        # Validate columns match user_context requirements
        columns_lower = [col.lower() for col in df.columns]
        assert "name" in columns_lower or any("name" in col.lower() for col in df.columns)
        assert "designation" in columns_lower or any("designation" in col.lower() for col in df.columns)


@pytest.mark.asyncio
async def test_e2e_simple_product_extraction(task_orchestrator_setup):
    """End-to-end test: Extract simple product data."""
    task_orchestrator = task_orchestrator_setup
    
    task_identification = TaskIdentificationResult(
        task_type=TaskType.EXTRACT_DATA_TO_SHEET,
        confidence=0.9,
        reasoning="User wants to extract product data",
        input={},
        output={},
    )
    
    task_input = {
        "selected_text": "Product A: $100, Stock: 50\nProduct B: $200, Stock: 30",
        "user_context": "Extract product data with name, price, and stock",
    }
    
    with patch('app.agents.data_extraction_agent.ReasoningEngine') as mock_reasoning_class:
        mock_reasoning = MagicMock()
        mock_reasoning.reason = AsyncMock(return_value={
            "result": '[{"name": "Product A", "price": 100, "stock": 50}, {"name": "Product B", "price": 200, "stock": 30}]',
            "metadata": {},
        })
        mock_reasoning_class.return_value = mock_reasoning
        
        result = await task_orchestrator.orchestrate_task(
            task_identification=task_identification,
            user_context=task_input["user_context"],
            context_metadata={},
            context_result=None,
            task_input=task_input,
        )
    
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_e2e_selected_text_only(task_orchestrator_setup):
    """End-to-end test: Extract with only selected_text (no user_context)."""
    task_orchestrator = task_orchestrator_setup
    
    task_identification = TaskIdentificationResult(
        task_type=TaskType.EXTRACT_DATA_TO_SHEET,
        confidence=0.9,
        reasoning="User wants to extract data",
        input={},
        output={},
    )
    
    task_input = {
        "selected_text": "Product A: $100, Product B: $200",
    }
    
    with patch('app.agents.data_extraction_agent.ReasoningEngine') as mock_reasoning_class:
        mock_reasoning = MagicMock()
        mock_reasoning.reason = AsyncMock(return_value={
            "result": '[{"name": "Product A", "price": 100}, {"name": "Product B", "price": 200}]',
            "metadata": {},
        })
        mock_reasoning_class.return_value = mock_reasoning
        
        result = await task_orchestrator.orchestrate_task(
            task_identification=task_identification,
            user_context="",
            context_metadata={},
            context_result=None,
            task_input=task_input,
        )
    
    assert result.status == "completed"
