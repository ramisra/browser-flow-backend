#!/usr/bin/env python3
"""Basic verification test that checks code structure and imports."""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from app.core.tools.excel_tools import ExcelTools
        print("✓ ExcelTools imported successfully")
    except Exception as e:
        print(f"✗ ExcelTools import failed: {e}")
        return False
    
    try:
        from app.agents.data_extraction_agent import DataExtractionAgent
        print("✓ DataExtractionAgent imported successfully")
    except Exception as e:
        print(f"✗ DataExtractionAgent import failed: {e}")
        return False
    
    try:
        from app.core.agents.prompt_manager import PromptManager
        print("✓ PromptManager imported successfully")
    except Exception as e:
        print(f"✗ PromptManager import failed: {e}")
        return False
    
    try:
        from app.core.agents.tool_integration import ToolIntegration
        print("✓ ToolIntegration imported successfully")
    except Exception as e:
        print(f"✗ ToolIntegration import failed: {e}")
        return False
    
    try:
        from app.core.agents.evaluator import Evaluator
        print("✓ Evaluator imported successfully")
    except Exception as e:
        print(f"✗ Evaluator import failed: {e}")
        return False
    
    try:
        from app.core.agents.reasoning_engine import ReasoningEngine
        print("✓ ReasoningEngine imported successfully")
    except Exception as e:
        print(f"✗ ReasoningEngine import failed: {e}")
        return False
    
    try:
        from app.services.task_orchestrator import TaskOrchestrator
        print("✓ TaskOrchestrator imported successfully")
    except Exception as e:
        print(f"✗ TaskOrchestrator import failed: {e}")
        return False
    
    try:
        from app.core.agent_registry import AgentRegistry
        print("✓ AgentRegistry imported successfully")
    except Exception as e:
        print(f"✗ AgentRegistry import failed: {e}")
        return False
    
    try:
        from app.core.tool_registry import ToolRegistry
        print("✓ ToolRegistry imported successfully")
    except Exception as e:
        print(f"✗ ToolRegistry import failed: {e}")
        return False
    
    return True


def test_excel_tools_initialization():
    """Test ExcelTools can be initialized (may fail if openpyxl/pandas not installed)."""
    print("\nTesting ExcelTools initialization...")
    
    try:
        from app.core.tools.excel_tools import ExcelTools
        
        # Try to initialize - this will fail if openpyxl/pandas not available
        try:
            excel_tools = ExcelTools(storage_dir="/tmp/test_excel")
            print("✓ ExcelTools initialized successfully")
            return True
        except ImportError as e:
            print(f"⚠ ExcelTools initialization requires openpyxl or pandas: {e}")
            print("  This is expected if dependencies are not installed")
            return True  # Not a failure, just missing dependency
        except Exception as e:
            print(f"✗ ExcelTools initialization failed: {e}")
            return False
    except Exception as e:
        print(f"✗ Could not test ExcelTools: {e}")
        return False


def test_agent_registry():
    """Test AgentRegistry can load from file."""
    print("\nTesting AgentRegistry...")
    
    try:
        from app.core.agent_registry import AgentRegistry
        
        registry = AgentRegistry()
        print("✓ AgentRegistry initialized")
        
        # Check if registry file exists
        registry_file = Path("app/config/agents_registry.json")
        if registry_file.exists():
            print(f"✓ Registry file exists: {registry_file}")
            
            # Try to get agent metadata
            metadata = registry.get_agent_metadata("data_extraction_agent")
            if metadata:
                print(f"✓ Found data_extraction_agent metadata")
                print(f"  - Task types: {metadata.task_types}")
                print(f"  - Capabilities: {metadata.capabilities}")
            else:
                print("⚠ data_extraction_agent metadata not found")
        else:
            print(f"⚠ Registry file not found: {registry_file}")
        
        return True
    except Exception as e:
        print(f"✗ AgentRegistry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_registry():
    """Test ToolRegistry has Excel tools."""
    print("\nTesting ToolRegistry...")
    
    try:
        from app.core.tool_registry import ToolRegistry
        
        registry = ToolRegistry()
        print("✓ ToolRegistry initialized")
        
        # Check for Excel tools
        excel_write = registry.get_tool("excel_write")
        excel_append = registry.get_tool("excel_append")
        excel_read = registry.get_tool("excel_read")
        
        if excel_write:
            print(f"✓ excel_write tool registered")
        else:
            print("✗ excel_write tool not found")
            return False
        
        if excel_append:
            print(f"✓ excel_append tool registered")
        else:
            print("✗ excel_append tool not found")
            return False
        
        if excel_read:
            print(f"✓ excel_read tool registered")
        else:
            print("✗ excel_read tool not found")
            return False
        
        return True
    except Exception as e:
        print(f"✗ ToolRegistry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_extraction_agent_structure():
    """Test DataExtractionAgent can be instantiated with mocks."""
    print("\nTesting DataExtractionAgent structure...")
    
    try:
        from app.agents.data_extraction_agent import DataExtractionAgent
        from app.core.agents.prompt_manager import PromptManager
        from app.core.agents.tool_integration import ToolIntegration
        from app.core.agents.evaluator import Evaluator
        from app.core.agents.reasoning_engine import ReasoningEngine
        from app.core.tool_registry import ToolRegistry
        from unittest.mock import MagicMock
        
        # Create components
        prompt_manager = PromptManager()
        tool_registry = ToolRegistry()
        tool_integration = ToolIntegration(tool_registry)
        evaluator = Evaluator()
        
        # Mock reasoning engine
        mock_reasoning = MagicMock()
        
        # Try to create agent (may fail if ExcelTools can't be initialized)
        try:
            from app.core.tools.excel_tools import ExcelTools
            excel_tools = ExcelTools(storage_dir="/tmp/test_excel")
        except ImportError:
            print("⚠ Skipping agent instantiation - ExcelTools requires dependencies")
            return True
        
        agent = DataExtractionAgent(
            agent_id="test_agent",
            prompt_manager=prompt_manager,
            tool_integration=tool_integration,
            evaluator=evaluator,
            reasoning_engine=mock_reasoning,
            excel_tools=excel_tools,
        )
        
        print("✓ DataExtractionAgent instantiated successfully")
        print(f"  - Agent ID: {agent.agent_id}")
        print(f"  - Has prompt_manager: {agent.prompt_manager is not None}")
        print(f"  - Has tool_integration: {agent.tool_integration is not None}")
        print(f"  - Has evaluator: {agent.evaluator is not None}")
        print(f"  - Has reasoning_engine: {agent.reasoning_engine is not None}")
        
        return True
    except Exception as e:
        print(f"✗ DataExtractionAgent structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("BASIC VERIFICATION TEST SUITE")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("ExcelTools Initialization", test_excel_tools_initialization()))
    results.append(("AgentRegistry", test_agent_registry()))
    results.append(("ToolRegistry", test_tool_registry()))
    results.append(("DataExtractionAgent Structure", test_data_extraction_agent_structure()))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    warnings = 0
    
    for test_name, result in results:
        if result is True:
            print(f"✅ {test_name}: PASSED")
            passed += 1
        elif result is False:
            print(f"❌ {test_name}: FAILED")
            failed += 1
        else:
            print(f"⚠️  {test_name}: WARNING")
            warnings += 1
    
    print()
    print(f"Total: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Warnings: {warnings}")
    print("=" * 60)
    
    if failed > 0:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1
    else:
        print("\n✅ All critical tests passed!")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
