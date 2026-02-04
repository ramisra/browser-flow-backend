#!/usr/bin/env python3
"""Manual test script for Excel extraction functionality."""

import asyncio
import sys
from pathlib import Path
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.tools.excel_tools import ExcelTools
from app.agents.data_extraction_agent import DataExtractionAgent
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.tool_integration import ToolIntegration
from app.core.agents.evaluator import Evaluator
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.tool_registry import ToolRegistry
from app.core.agents.agent_context import AgentContext
from app.models.task_identification import TaskIdentificationResult
from app.core.task_types import TaskType


async def test_excel_tools():
    """Test Excel tools functionality."""
    print("=" * 60)
    print("TEST 1: Excel Tools - Basic Creation")
    print("=" * 60)
    
    # Create temporary directory
    temp_dir = Path("/tmp/test_excel_storage")
    temp_dir.mkdir(exist_ok=True)
    excel_dir = temp_dir / "excel"
    excel_dir.mkdir(exist_ok=True)
    
    excel_tools = ExcelTools(storage_dir=str(excel_dir))
    
    # Test data
    data = [
        {"name": "Product A", "price": 100, "stock": 50},
        {"name": "Product B", "price": 200, "stock": 30},
    ]
    columns = ["name", "price", "stock"]
    
    # Create Excel file
    file_path = await excel_tools.create_excel_file(data=data, columns=columns)
    print(f"✓ Excel file created: {file_path}")
    
    # Verify file exists
    assert Path(file_path).exists(), "Excel file should exist"
    print(f"✓ File exists: {Path(file_path).exists()}")
    
    # Read and validate
    df = pd.read_excel(file_path, engine="openpyxl")
    print(f"✓ File read successfully: {len(df)} rows")
    assert len(df) == 2, f"Expected 2 rows, got {len(df)}"
    assert list(df.columns) == columns, f"Columns mismatch: {list(df.columns)}"
    assert df.iloc[0]["name"] == "Product A", "First row name mismatch"
    print(f"✓ Data validation passed")
    
    # Test append
    new_data = [{"name": "Product C", "price": 300, "stock": 20}]
    await excel_tools.append_to_excel(file_path, new_data, columns)
    df = pd.read_excel(file_path, engine="openpyxl")
    assert len(df) == 3, f"Expected 3 rows after append, got {len(df)}"
    print(f"✓ Append functionality works: {len(df)} rows")
    
    print("\n✅ Excel Tools Test PASSED\n")


async def test_data_extraction_agent():
    """Test DataExtractionAgent with mocked reasoning engine."""
    print("=" * 60)
    print("TEST 2: Data Extraction Agent - Lead Tracking")
    print("=" * 60)
    
    # Create temporary directory
    temp_dir = Path("/tmp/test_excel_storage")
    excel_dir = temp_dir / "excel"
    excel_dir.mkdir(exist_ok=True)
    
    # Setup components
    prompt_manager = PromptManager()
    tool_registry = ToolRegistry()
    tool_integration = ToolIntegration(tool_registry)
    evaluator = Evaluator()
    excel_tools = ExcelTools(storage_dir=str(excel_dir))
    
    # Mock reasoning engine
    mock_reasoning = MagicMock(spec=ReasoningEngine)
    mock_reasoning.reason = AsyncMock(return_value={
        "result": '''[
            {
                "name": "Ratikesh Misra",
                "designation": "VP engineering",
                "company": "Flobiz",
                "total_connection": 140
            },
            {
                "name": "Unknown",
                "designation": "CTO",
                "company": "furrl",
                "total_connection": null
            }
        ]''',
        "metadata": {},
    })
    
    # Create agent
    agent = DataExtractionAgent(
        agent_id="test_agent",
        prompt_manager=prompt_manager,
        tool_integration=tool_integration,
        evaluator=evaluator,
        reasoning_engine=mock_reasoning,
        excel_tools=excel_tools,
    )
    
    # Test input
    task_input = {
        "selected_text": "140 connection, Ratikesh Misra, VP engineering Flobiz, CTO furrl",
        "user_context": "Create the excel sheet for tracking lead with name, designation and total connection",
    }
    
    # Execute agent
    result = await agent.execute(task_input)
    
    print(f"✓ Agent execution status: {result.status}")
    assert result.status == "completed", f"Expected 'completed', got '{result.status}'"
    
    print(f"✓ Excel file path: {result.excel_file_path}")
    assert result.excel_file_path is not None, "Excel file path should not be None"
    assert Path(result.excel_file_path).exists(), "Excel file should exist"
    
    # Validate Excel content
    df = pd.read_excel(result.excel_file_path, engine="openpyxl")
    print(f"✓ Excel file has {len(df)} rows")
    print(f"✓ Columns: {list(df.columns)}")
    
    # Check columns match requirements
    columns_lower = [col.lower() for col in df.columns]
    has_name = "name" in columns_lower or any("name" in col.lower() for col in df.columns)
    has_designation = "designation" in columns_lower or any("designation" in col.lower() for col in df.columns)
    
    print(f"✓ Has name column: {has_name}")
    print(f"✓ Has designation column: {has_designation}")
    
    assert has_name, "Should have name column"
    assert has_designation, "Should have designation column"
    
    print(f"✓ Extracted data: {len(result.extracted_data) if result.extracted_data else 0} rows")
    
    print("\n✅ Data Extraction Agent Test PASSED\n")


async def test_simple_product_extraction():
    """Test simple product data extraction."""
    print("=" * 60)
    print("TEST 3: Data Extraction Agent - Simple Product Data")
    print("=" * 60)
    
    # Create temporary directory
    temp_dir = Path("/tmp/test_excel_storage")
    excel_dir = temp_dir / "excel"
    excel_dir.mkdir(exist_ok=True)
    
    # Setup components
    prompt_manager = PromptManager()
    tool_registry = ToolRegistry()
    tool_integration = ToolIntegration(tool_registry)
    evaluator = Evaluator()
    excel_tools = ExcelTools(storage_dir=str(excel_dir))
    
    # Mock reasoning engine
    mock_reasoning = MagicMock(spec=ReasoningEngine)
    mock_reasoning.reason = AsyncMock(return_value={
        "result": '''[
            {"name": "Product A", "price": 100, "stock": 50},
            {"name": "Product B", "price": 200, "stock": 30}
        ]''',
        "metadata": {},
    })
    
    # Create agent
    agent = DataExtractionAgent(
        agent_id="test_agent_2",
        prompt_manager=prompt_manager,
        tool_integration=tool_integration,
        evaluator=evaluator,
        reasoning_engine=mock_reasoning,
        excel_tools=excel_tools,
    )
    
    # Test input
    task_input = {
        "selected_text": "Product A: $100, Stock: 50\nProduct B: $200, Stock: 30",
        "user_context": "Extract product data with name, price, and stock",
    }
    
    # Execute agent
    result = await agent.execute(task_input)
    
    print(f"✓ Agent execution status: {result.status}")
    assert result.status == "completed"
    
    print(f"✓ Excel file path: {result.excel_file_path}")
    assert Path(result.excel_file_path).exists()
    
    # Validate Excel content
    df = pd.read_excel(result.excel_file_path, engine="openpyxl")
    print(f"✓ Excel file has {len(df)} rows")
    print(f"✓ Columns: {list(df.columns)}")
    
    assert len(df) > 0, "Should have at least one row"
    
    print("\n✅ Simple Product Extraction Test PASSED\n")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("EXCEL EXTRACTION TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        await test_excel_tools()
        await test_data_extraction_agent()
        await test_simple_product_extraction()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
