"""Semantic knowledge service for RAG-based knowledge retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from app.core.agents.agent_context import AgentContext
from app.services.embedding import EmbeddingService

if TYPE_CHECKING:
    from app.repositories.user_context_repository import UserContextRepository


class SemanticKnowledgeService:
    """RAG-based semantic knowledge retrieval service."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        context_repository: Optional[UserContextRepository] = None,
    ):
        """Initialize the semantic knowledge service.

        Args:
            embedding_service: Embedding service for generating embeddings
            context_repository: User context repository for querying contexts (optional for process_context-only use)
        """
        self.embedding_service = embedding_service
        self.context_repository = context_repository

    async def retrieve_relevant_context(
        self,
        query: str,
        user_guest_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context using semantic search.

        Args:
            query: Query string for semantic search
            user_guest_id: Optional user guest ID to filter contexts
            limit: Maximum number of results

        Returns:
            List of relevant context dictionaries
        """
        if not query or not query.strip():
            return []

        if not self.context_repository:
            return []

        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query)
        if not query_embedding:
            return []

        # Search for similar contexts
        try:
            contexts = await self.context_repository.search_similar_contexts(
                query_embedding=query_embedding,
                user_guest_id=user_guest_id,
                limit=limit,
            )

            # Convert to dictionary format
            results = []
            for context in contexts:
                results.append({
                    "context_id": str(context.context_id),
                    "raw_content": context.raw_content,
                    "context_tags": context.context_tags,
                    "url": context.url,
                    "user_defined_context": context.user_defined_context,
                    "similarity_score": getattr(context, "similarity_score", None),
                })

            return results
        except Exception as e:
            print(f"Error retrieving relevant context: {e}")
            return []

    async def enrich_agent_context(
        self,
        agent_context: AgentContext,
        query: str,
    ) -> AgentContext:
        """Enrich agent context with relevant knowledge.

        Args:
            agent_context: Agent context to enrich
            query: Query string for semantic search

        Returns:
            Enriched agent context
        """
        # Retrieve relevant contexts
        relevant_contexts = await self.retrieve_relevant_context(
            query=query,
            user_guest_id=str(agent_context.user_guest_id) if agent_context.user_guest_id else None,
            limit=5,
        )

        # Add to context metadata
        if relevant_contexts:
            agent_context.context_metadata["semantic_knowledge"] = relevant_contexts

        return agent_context

    async def process_context(
        self,
        urls: Optional[List[str]] = None,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Process context or URLs with Claude to extract tags, content, and metadata.

        Same logic as run_url_context_agent: if context is provided use it directly;
        otherwise fetch each URL. Returns {"contexts": [{"url", "title", "tags", "content", "short_summary"}, ...]}.
        """
        if context:
            prompt = f"""
You are a research assistant.

You are given context content. Your task is to:
- Analyze the provided context content.
- Extract the main textual content.
- Assign 2–5 descriptive tags that summarize what the content is about.
  Examples of tags: "research paper", "ICLR paper", "documentation", "API reference",
  "blog post", "product marketing", "landing page", "tutorial", "news", "other".
- Return the result as a JSON object with:
  - url (if available from context, otherwise "provided_context")
  - title (if available)
  - tags (list of strings)
  - content (the main textual content)
  - short_summary (2–3 sentences).

After you have built the JSON result:
- Call the Bash tool ONCE with a command that writes this JSON to a file named
  `url_context_output.json` in the current working directory.
- Overwrite any existing file of that name.
- Do not ask the user for confirmation; just write the file.

Here is the context:

{context}
"""
            allowed_tools = ["Read", "Edit", "Glob", "Bash"]
            system_prompt = (
                "You are a senior research assistant. "
                "You have been provided with context directly - do not use web fetch tools. "
                "Be accurate and concise when assigning tags. "
                "When you have your final JSON result, use the Bash tool to write it "
                "to a file called url_context_output.json in the current working directory."
            )
        elif urls:
            urls_markdown = "\n".join(f"- {u}" for u in urls)
            prompt = f"""
You are a research assistant.

You are given a list of URLs. For each URL:
- Use the web fetch tool to open and read the page.
- Extract the main textual content (ignore navigation, boilerplate, and cookie banners).
- Assign 2–5 descriptive tags that summarize what the page is about.
  Examples of tags: "research paper", "ICLR paper", "documentation", "API reference",
  "blog post", "product marketing", "landing page", "tutorial", "news", "other".
- Return the result as a small JSON object for each URL with:
  - url
  - title (if available)
  - tags (list of strings)
  - content (the main textual content of the page)
  - short_summary (2–3 sentences).

After you have built the full JSON result for all URLs:
- Call the Bash tool ONCE with a command that writes this JSON to a file named
  `url_context_output.json` in the current working directory.
- Overwrite any existing file of that name.
- Do not ask the user for confirmation; just write the file.

Here are the URLs:

{urls_markdown}
"""
            allowed_tools = ["WebFetch", "Read", "Edit", "Glob", "Bash"]
            system_prompt = (
                "You are a senior research assistant. "
                "Always use the web fetch tool to open URLs instead of guessing content. "
                "Be accurate and concise when assigning tags. "
                "When you have your final JSON result, use the Bash tool to write it "
                "to a file called url_context_output.json in the current working directory."
            )
        else:
            raise ValueError("Either urls or context must be provided")

        context_output_path = Path("url_context_output.json")

        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode="acceptEdits",
                system_prompt=system_prompt,
            ),
        ):
            print(f"Message: {message}")
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text") and block.text:
                        print(block.text)
                    elif hasattr(block, "name"):
                        print(f"Tool call: {block.name}")
            elif isinstance(message, ResultMessage):
                pass

        parsed_result: Optional[Dict[str, Any]] = None
        if context_output_path.exists():
            try:
                with open(context_output_path, "r", encoding="utf-8") as f:
                    file_content = f.read().strip()
                    if file_content:
                        parsed_result = json.loads(file_content)
                        print(f"Successfully parsed context from {context_output_path}")
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON from {context_output_path}: {e}")
            except Exception as e:
                print(f"Error reading {context_output_path}: {e}")
        else:
            print(f"Warning: {context_output_path} not found after agent execution")

        if parsed_result:
            if isinstance(parsed_result, list):
                return {"contexts": parsed_result}
            return {"contexts": [parsed_result]}

        return None


__all__ = ["SemanticKnowledgeService"]
