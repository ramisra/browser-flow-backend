"""Shared test fixtures and configuration."""

import tempfile
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_types import TaskType
from app.models.task_identification import TaskIdentificationResult
from app.core.tools.excel_tools import ExcelTools
from app.core.tool_registry import ToolRegistry
from app.services.embedding import EmbeddingService


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory for tests."""
    temp_dir = tempfile.mkdtemp()
    excel_dir = Path(temp_dir) / "excel"
    excel_dir.mkdir(parents=True)
    yield excel_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def excel_tools(temp_storage_dir):
    """Create ExcelTools instance with temporary storage."""
    return ExcelTools(storage_dir=str(temp_storage_dir))


@pytest.fixture
def mock_task_identification_result():
    """Mock TaskIdentificationResult for EXTRACT_DATA_TO_SHEET."""
    return TaskIdentificationResult(
        task_type=TaskType.EXTRACT_DATA_TO_SHEET,
        confidence=0.9,
        reasoning="User wants to extract data to Excel",
        input={"data_source": "text", "fields": ["name", "price"]},
        output={"format": "excel", "columns": ["name", "price"]},
    )


@pytest.fixture
def sample_extraction_data():
    """Sample data for extraction tests."""
    return [
        {"name": "Product A", "price": 100, "stock": 50},
        {"name": "Product B", "price": 200, "stock": 30},
    ]


@pytest.fixture
def sample_lead_data():
    """Sample lead tracking data."""
    return [
        {
            "name": "Ratikesh Misra",
            "designation": "VP engineering",
            "company": "Flobiz",
            "total_connection": 140,
        },
        {
            "name": "Unknown",
            "designation": "CTO",
            "company": "furrl",
            "total_connection": None,
        },
    ]


@pytest.fixture
def tool_registry():
    """Create ToolRegistry instance."""
    return ToolRegistry()


@pytest.fixture
def embedding_service():
    """Create EmbeddingService instance (may need API key)."""
    return EmbeddingService()


@pytest.fixture
def sample_selected_text():
    """Sample selected text for extraction."""
    return "140 connection, Ratikesh Misra, VP engineering Flobiz, CTO furrl"


@pytest.fixture
def sample_user_context():
    """Sample user context for extraction."""
    return "Create the excel sheet for tracking lead with name, designation and total connection"
