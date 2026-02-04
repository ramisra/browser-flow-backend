"""Agent spawner factory for instantiating agents."""

from typing import Any, Dict, List, Optional, Type
import os
from app.core.agents.agent_context import AgentContext
from app.core.agents.base_agent import BaseAgent
from app.core.agents.evaluator import Evaluator
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.agents.tool_integration import ToolIntegration
from app.core.tool_registry import ToolRegistry
from app.core.tools.excel_mcp_tools import create_excel_mcp_server
from app.core.tools.excel_tools import ExcelTools
from app.core.tools.notion_client import NotionClient
from app.core.tools.notion_mcp_tools import create_notion_mcp_server
from app.models.agent_metadata import AgentMetadata
from app.services.composio_tool_provider import (
    create_composio_mcp_server,
    get_toolkits_for_missing_tools,
)
from app.services.embedding import EmbeddingService
from app.services.semantic_knowledge_service import SemanticKnowledgeService


class AgentSpawner:
    """Factory for creating agent instances with all internal components."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        embedding_service: EmbeddingService,
        semantic_knowledge_service: Optional[SemanticKnowledgeService] = None,
        excel_tools: Optional[ExcelTools] = None,
        notion_client: Optional[NotionClient] = None,
    ):
        """Initialize the agent spawner.

        Args:
            tool_registry: Tool registry instance
            embedding_service: Embedding service instance
            semantic_knowledge_service: Optional semantic knowledge service
            excel_tools: Optional Excel tools instance for agents that need it
            notion_client: Optional Notion client (e.g. for tests); note-taking agent uses this
        """
        self.tool_registry = tool_registry
        self.embedding_service = embedding_service
        self.semantic_knowledge_service = semantic_knowledge_service
        self.excel_tools = excel_tools or ExcelTools()
        self.notion_client = notion_client
        self.mcp_servers_pool = {
            "excel": create_excel_mcp_server(self.excel_tools),
            "notion": create_notion_mcp_server(),
        }

    def _get_missing_tools(
        self,
        required_tools: List[str],
        mcp_servers: Dict[str, Any],
    ) -> List[str]:
        """Return required tools not satisfied by the current MCP servers.

        A tool like mcp__excel__excel_write is satisfied if we have the
        "excel" server. Composio tools would be mcp__composio__*.
        """
        if not required_tools:
            return []
        server_names = set(mcp_servers.keys())
        missing = []
        for tool in required_tools:
            if not tool.startswith("mcp__"):
                missing.append(tool)
                continue
            parts = tool.split("__", 2)
            if len(parts) >= 2 and parts[1] not in server_names:
                missing.append(tool)
        return missing

    async def spawn_agent(
        self,
        agent_class: Type[BaseAgent],
        agent_context: AgentContext,
        agent_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        agent_metadata: Optional[AgentMetadata] = None,
    ) -> BaseAgent:
        """Spawn an agent instance with all internal components.

        Args:
            agent_class: Agent class to instantiate
            agent_context: Agent context
            agent_id: Optional agent ID (generated if not provided)
            config: Optional agent configuration

        Returns:
            Instantiated agent instance
        """
        config = config or {}

        # Generate agent ID if not provided
        if not agent_id:
            agent_id = f"{agent_class.__name__.lower()}_{id(agent_class)}"

        # Create internal components
        prompt_manager = PromptManager(
            system_prompt=config.get("system_prompt"),
            prompt_templates=config.get("prompt_templates"),
        )

        tool_integration = ToolIntegration(self.tool_registry)

        evaluator = Evaluator(
            validation_rules=config.get("validation_rules"),
        )

        reasoning_engine = ReasoningEngine(
            api_key=config.get("api_key"),
            model=config.get("model", "claude-3-5-sonnet-20241022"),
            system_prompt=config.get("reasoning_system_prompt"),
        )

        # Create agent instance
        # Check if agent class accepts excel_tools parameter
        import inspect
        sig = inspect.signature(agent_class.__init__)
        params = sig.parameters
        
        agent_kwargs = {
            "agent_id": agent_id,
            "prompt_manager": prompt_manager,
            "tool_integration": tool_integration,
            "evaluator": evaluator,
            "reasoning_engine": reasoning_engine,
            "semantic_knowledge": self.semantic_knowledge_service,
            "agent_context": agent_context,
        }
        
        # Add excel_tools if agent accepts it
        if "excel_tools" in params:
            agent_kwargs["excel_tools"] = self.excel_tools

        # Add notion_client if agent accepts it (e.g. NoteTakingAgent)
        if "notion_client" in params:
            agent_kwargs["notion_client"] = (
                self.notion_client if self.notion_client is not None else NotionClient()
            )

        if agent_metadata:
            required_tools = agent_metadata.required_tools
            required_mcp_servers = agent_metadata.required_mcp_servers
            mcp_servers = {
                name: server
                for name, server in self.mcp_servers_pool.items()
                if name in required_mcp_servers
            }
        
            # Composio fallback: add Composio MCP server when tools are missing
            # or when composio is explicitly required
            use_composio = getattr(
                agent_metadata, "use_composio_fallback", True
            )
            composio_toolkits = getattr(
                agent_metadata, "composio_toolkits", None
            )

            need_composio = (
                "composio" in required_mcp_servers
                or (
                    use_composio
                    and self._get_missing_tools(required_tools, mcp_servers)
                )
            )

            if need_composio:
                user_id = (
                   os.getenv("USER_ID")
                )
                toolkits = composio_toolkits
                if not toolkits and use_composio:
                    missing = self._get_missing_tools(
                        required_tools, mcp_servers
                    )
                    toolkits = get_toolkits_for_missing_tools(missing)
                if not toolkits:
                    toolkits = ["composio"]
                print(f"creating composio mcp server with toolkits: {toolkits}; user_id: {user_id}")
                composio_server = create_composio_mcp_server(
                    user_id=user_id, toolkits=toolkits
                )
                if composio_server:
                    mcp_servers["composio"] = composio_server

            if "allowed_tools" in params:
                agent_kwargs["allowed_tools"] = required_tools
            if "mcp_servers" in params:
                agent_kwargs["mcp_servers"] = mcp_servers

        print(f"agent kwargs: {agent_kwargs}")
        agent = agent_class(**agent_kwargs)

        return agent


__all__ = ["AgentSpawner"]
