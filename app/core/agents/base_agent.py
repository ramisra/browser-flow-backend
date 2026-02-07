"""Base agent class with internal structure."""

from typing import Any, Dict, List, Optional

from app.core.agents.agent_context import AgentContext
from app.core.agents.evaluator import Evaluator, EvaluationResult
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.agents.tool_integration import ToolIntegration
from app.models.agent_result import AgentResult


class BaseAgent:
    """Base class for all agents with internal components."""

    def __init__(
        self,
        agent_id: str,
        prompt_manager: PromptManager,
        tool_integration: ToolIntegration,
        evaluator: Evaluator,
        reasoning_engine: ReasoningEngine,
        semantic_knowledge: Optional[Any] = None,  # SemanticKnowledgeService
        agent_context: Optional[AgentContext] = None,
    ):
        """Initialize the base agent.

        Args:
            agent_id: Unique agent identifier
            prompt_manager: Prompt management component
            tool_integration: Tool/MCP integration component
            evaluator: Evaluation component
            reasoning_engine: Reasoning engine component
            semantic_knowledge: Optional semantic knowledge service
            agent_context: Optional agent context
        """
        self.agent_id = agent_id
        self.prompt_manager = prompt_manager
        self.tool_integration = tool_integration
        self.evaluator = evaluator
        self.reasoning_engine = reasoning_engine
        self.semantic_knowledge = semantic_knowledge
        self.agent_context = agent_context

    async def execute(
        self, task_input: Dict[str, Any], agent_context: Optional[AgentContext] = None
    ) -> AgentResult:
        """Execute the agent with given task input.

        Subclasses must implement execute() by calling the reasoning engine
        (via self.reason()) with prompt, applicable tools, and context to
        perform the task; they may also call self.use_tool() for tool
        execution and return an AgentResult.

        Args:
            task_input: Task input dictionary
            agent_context: Optional agent context

        Returns:
            AgentResult with execution results

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement execute()")

    async def reason(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        mcp_servers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform reasoning using the reasoning engine.

        Args:
            prompt: Reasoning prompt
            context: Optional context dictionary
            tools: Optional list of allowed tool names

        Returns:
            Reasoning result dictionary
        """
        return await self.reasoning_engine.reason(
            prompt,
            context,
            tools,
            mcp_servers,
            caller=self.__class__.__name__,
        )

    async def use_tool(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Any:
        """Use a tool via tool integration.

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            Tool execution result
        """
        return await self.tool_integration.execute_tool(tool_name, params)

    async def evaluate(
        self,
        result: Any,
        expected_output: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Evaluate a result.

        Args:
            result: Result to evaluate
            expected_output: Optional expected output structure

        Returns:
            EvaluationResult
        """
        return await self.evaluator.evaluate(result, expected_output)

    async def retrieve_knowledge(
        self, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge using semantic knowledge service.

        Args:
            query: Query string
            limit: Maximum number of results

        Returns:
            List of relevant context dictionaries

        Raises:
            ValueError: If semantic knowledge service not available
        """
        if not self.semantic_knowledge:
            return []

        return await self.semantic_knowledge.retrieve_relevant_context(
            query, limit
        )

    def get_available_tools(self) -> List[Any]:
        """Get all available tools.

        Returns:
            List of available tools
        """
        return self.tool_integration.get_available_tools()


__all__ = ["BaseAgent"]
