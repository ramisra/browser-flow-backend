"""Note-taking agent: structured pipeline (search → append or create) via NotionClient."""

import json
import re
from typing import Any, Dict, List, Optional

from app.core.agents.agent_context import AgentContext
from app.core.agents.base_agent import BaseAgent
from app.core.agents.evaluator import Evaluator
from app.core.agents.prompt_manager import PromptManager
from app.core.agents.reasoning_engine import ReasoningEngine
from app.core.agents.tool_integration import ToolIntegration
from app.core.tools.notion_client import NotionClient, NotionClientError
from app.models.agent_result import AgentResult

# Default sort for Notion search (matches notion_client.DEFAULT_SEARCH_SORT)
DEFAULT_SEARCH_SORT = {
    "direction": "descending",
    "timestamp": "last_edited_time",
}


class NoteTakingAgent(BaseAgent):
    """Agent for creating and organizing notes in Notion via a structured pipeline.

    Flow: LLM (search payload) → execute search → decide page found? →
    if yes: LLM (append payload) → execute append_block_children → return;
    if no: LLM (create payload) → execute create_page → return.
    Uses NotionClient directly; LLM is used only for generating API payloads (no tools).
    """

    def __init__(
        self,
        agent_id: str,
        prompt_manager: PromptManager,
        tool_integration: ToolIntegration,
        evaluator: Evaluator,
        reasoning_engine: ReasoningEngine,
        mcp_servers: Optional[Dict[str, Any]] = None,
        allowed_tools: Optional[List[str]] = None,
        semantic_knowledge: Optional[Any] = None,
        notion_client: Optional[NotionClient] = None,
        agent_context: Optional[AgentContext] = None,
    ) -> None:
        """Initialize the note-taking agent."""
        super().__init__(
            agent_id=agent_id,
            prompt_manager=prompt_manager,
            tool_integration=tool_integration,
            evaluator=evaluator,
            reasoning_engine=reasoning_engine,
            semantic_knowledge=semantic_knowledge,
            agent_context=agent_context,
        )
        self.mcp_servers = mcp_servers
        self.allowed_tools = allowed_tools
        self._notion_client = notion_client or NotionClient()

        system_prompt = (
            "You are a note-taking assistant that creates and organizes notes in Notion. "
            "You do not call tools yourself. You only output JSON payloads when asked. "
            "The system will first ask you for a Notion search payload (query, optional filter/sort). "
            "Then, if a page is found, you will be asked for an append payload (page_id, blocks). "
            "If no page is found, you will be asked for a create_page payload (parent_page_id, title, children). "
            "Always respond with a single JSON object only, no markdown or explanation."
        )
        self.prompt_manager.set_system_prompt(system_prompt)

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract the first {...} from text and parse as JSON."""
        if not text:
            return None
        try:
            start_idx = text.find("{")
            end_idx = text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                return json.loads(text[start_idx:end_idx])
        except Exception:
            return None
        return None

    def _extract_page_url(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r"https?://[^\s]+notion[^\s]+", text)
        if match:
            return match.group(0)
        return None

    def _extract_page_id(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(
            r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
            text,
        )
        if match:
            return match.group(0)
        return None

    async def execute(
        self, task_input: Dict[str, Any], agent_context: Optional[AgentContext] = None
    ) -> AgentResult:
        """Execute note-taking via structured pipeline: search → append or create."""
        selected_text = (task_input.get("selected_text") or "").strip()
        user_context = (task_input.get("user_context") or "").strip()
        urls = task_input.get("urls") or []
        if agent_context and not user_context:
            user_context = (agent_context.user_context or "").strip()

        print(f"[NoteTakingAgent] execute started: user_context={repr((user_context[:80] + '...') if len(user_context) > 80 else user_context)}, selected_text_len={len(selected_text)}, urls={urls}")
        try:
            # --- Step 1: LLM → search payload, then execute and parse ---
            print("[NoteTakingAgent] Step 1: requesting search payload from LLM")
            search_prompt = (
                "Return ONLY a single JSON object suitable for the Notion search API.\n"
                "Required: \"query\" (string). Optional: \"filter\" (object), \"sort\" (object with "
                "\"direction\" and \"timestamp\", e.g. {\"direction\": \"descending\", \"timestamp\": \"last_edited_time\"}), "
                "\"page_size\" (number), \"start_cursor\" (string).\n"
                "User context (use to derive search query):\n"
                f"{user_context}\n\n"
                "Content to save (for context):\n"
                f"{selected_text}\n"
            )
            if urls:
                search_prompt += f"\nSource URLs: {', '.join(urls)}\n"
            search_prompt += "\nOutput only the JSON object, no other text."

            search_result = await self.reason(
                search_prompt,
                context={"user_context": user_context, "urls": urls},
                tools=None,
                mcp_servers=None,
            )
            reasoning_text = search_result.get("result") or ""
            if search_result.get("error"):
                print(f"[NoteTakingAgent] Step 1 failed: LLM error={search_result.get('error')}")
                return AgentResult(
                    status="failed",
                    result={},
                    error=search_result.get("error", "Search payload reasoning failed"),
                )
            payload = self._extract_json_object(reasoning_text)
            if not payload or not isinstance(payload.get("query"), str):
                print("[NoteTakingAgent] Step 1 failed: invalid or missing search payload (need 'query' string)")
                return AgentResult(
                    status="failed",
                    result={},
                    error="Invalid or missing search payload: need at least \"query\" (string)",
                )
            query = payload["query"].strip()
            if not query:
                print("[NoteTakingAgent] Step 1 failed: search query is empty")
                return AgentResult(
                    status="failed",
                    result={},
                    error="Search payload query cannot be empty",
                )
            print(f"[NoteTakingAgent] Step 1: parsed search payload query={repr(query)}")
            filter_obj = payload.get("filter") if isinstance(payload.get("filter"), dict) else None
            sort = payload.get("sort") if isinstance(payload.get("sort"), dict) else None
            page_size = payload.get("page_size") if isinstance(payload.get("page_size"), int) else 100
            start_cursor = payload.get("start_cursor") if isinstance(payload.get("start_cursor"), str) else None

            print(f"[NoteTakingAgent] Step 1: calling Notion search with query={repr(query)}")
            search_response = await self._notion_client.search(
                query=query,
                filter_obj=filter_obj,
                sort=sort or DEFAULT_SEARCH_SORT,
                page_size=page_size,
                start_cursor=start_cursor,
            )
            results = search_response.get("results") or []
            most_relevant_page_id = search_response.get("most_relevant_page_id")
            most_relevant_url = search_response.get("most_relevant_url")
            print(f"[NoteTakingAgent] Step 1: search returned {len(results)} results, most_relevant_page_id={most_relevant_page_id}")

            # --- Step 2: Decide "page found per user context" (v1: first result if any) ---
            page_exists = len(results) > 0
            print(f"[NoteTakingAgent] Step 2: page_exists={page_exists}")
            target_page_id = most_relevant_page_id
            target_page_url = most_relevant_url
            target_title_plain = results[0].get("title_plain") if results else None

            if page_exists:
                # --- Step 3a: LLM append payload → execute append_block_children → return ---
                print(f"[NoteTakingAgent] Step 3a: page found, requesting append payload from LLM (target_page_id={target_page_id})")
                append_prompt = (
                    "Return ONLY a single JSON object to append blocks to an existing Notion page.\n"
                    "Keys: \"page_id\" (string, the target page id), \"blocks\" (array of block objects). "
                    "Each block: {\"type\": \"paragraph\"|\"heading_1\"|\"heading_2\"|\"to_do\"|\"bulleted_list_item\"|\"numbered_list_item\"|\"quote\"|\"code\"|\"divider\", "
                    "\"content\": string, optional \"checked\" (boolean for to_do), optional \"language\" (for code)}. "
                    "Optional: \"position\" (object).\n"
                    f"Target page_id: {target_page_id}\n"
                    f"Target page title (if any): {target_title_plain}\n"
                    f"User context: {user_context}\n\n"
                    f"Content to append:\n{selected_text}\n\n"
                    "Output only the JSON object, no other text."
                )
                append_result = await self.reason(
                    append_prompt,
                    context={"user_context": user_context, "page_id": target_page_id},
                    tools=None,
                    mcp_servers=None,
                )
                append_text = append_result.get("result") or ""
                if append_result.get("error"):
                    print(f"[NoteTakingAgent] Step 3a failed: LLM error={append_result.get('error')}")
                    return AgentResult(
                        status="failed",
                        result={},
                        error=append_result.get("error", "Append payload reasoning failed"),
                    )
                append_payload = self._extract_json_object(append_text)
                if not append_payload or not append_payload.get("page_id") or not append_payload.get("blocks"):
                    print("[NoteTakingAgent] Step 3a failed: invalid append payload (need page_id and blocks)")
                    return AgentResult(
                        status="failed",
                        result={},
                        error="Invalid append payload: need \"page_id\" and \"blocks\" array",
                    )
                block_id = append_payload["page_id"]
                children = append_payload["blocks"]
                position = append_payload.get("position") if isinstance(append_payload.get("position"), dict) else None
                print(f"[NoteTakingAgent] Step 3a: calling append_block_children block_id={block_id}, blocks_count={len(children)}")

                append_response = await self._notion_client.append_block_children(
                    block_id=block_id,
                    children=children,
                    position=position,
                )
                out_page_id = append_response.get("page_id") or block_id
                summary = "Note appended to existing page in Notion."
                content_preview = (selected_text[:200] + "…") if len(selected_text) > 200 else selected_text
                print(f"[NoteTakingAgent] Step 3a completed: notion_page_id={out_page_id}, notion_page_url={target_page_url}")
                return AgentResult(
                    status="completed",
                    result={
                        "notion_page_id": out_page_id,
                        "notion_page_url": target_page_url,
                        "summary": summary,
                        "content_preview": content_preview,
                    },
                )
            else:
                # --- Step 3b: LLM create_page payload → execute create_page → return ---
                print("[NoteTakingAgent] Step 3b: no page found, requesting create_page payload from LLM")
                create_prompt = (
                    "Return ONLY a single JSON object to create a new Notion page.\n"
                    "Keys: optional \"parent_page_id\" (string; omit to use default), \"title\" (string), "
                    "optional \"children\" (array of block objects: {\"type\", \"content\", optional \"checked\", \"language\"}).\n"
                    f"User context: {user_context}\n\n"
                    f"Content to save (use to build title and optional initial blocks):\n{selected_text}\n\n"
                    "Output only the JSON object, no other text."
                )
                create_result = await self.reason(
                    create_prompt,
                    context={"user_context": user_context},
                    tools=None,
                    mcp_servers=None,
                )
                create_text = create_result.get("result") or ""
                if create_result.get("error"):
                    print(f"[NoteTakingAgent] Step 3b failed: LLM error={create_result.get('error')}")
                    return AgentResult(
                        status="failed",
                        result={},
                        error=create_result.get("error", "Create payload reasoning failed"),
                    )
                create_payload = self._extract_json_object(create_text)
                if not create_payload or not isinstance(create_payload.get("title"), str):
                    print("[NoteTakingAgent] Step 3b failed: invalid create payload (need title string)")
                    return AgentResult(
                        status="failed",
                        result={},
                        error="Invalid create payload: need \"title\" (string)",
                    )
                parent_page_id = create_payload.get("parent_page_id")
                if parent_page_id is not None and not isinstance(parent_page_id, str):
                    parent_page_id = None
                title = (create_payload.get("title") or "").strip() or "New note"
                children = create_payload.get("children") if isinstance(create_payload.get("children"), list) else None
                print(f"[NoteTakingAgent] Step 3b: calling create_page title={repr(title)}, parent_page_id={parent_page_id}, children_count={len(children) if children else 0}")

                create_response = await self._notion_client.create_page(
                    parent_page_id=parent_page_id or None,
                    title=title,
                    children=children,
                )
                out_page_id = create_response.get("page_id")
                out_url = create_response.get("url")
                summary = "Note created in Notion."
                content_preview = (selected_text[:200] + "…") if len(selected_text) > 200 else selected_text
                print(f"[NoteTakingAgent] Step 3b completed: notion_page_id={out_page_id}, notion_page_url={out_url}")
                return AgentResult(
                    status="completed",
                    result={
                        "notion_page_id": out_page_id,
                        "notion_page_url": out_url,
                        "summary": summary,
                        "content_preview": content_preview,
                    },
                )
        except NotionClientError as e:
            print(f"[NoteTakingAgent] execute failed: NotionClientError {e}")
            return AgentResult(
                status="failed",
                result={},
                error=str(e),
            )
        except Exception as e:
            print(f"[NoteTakingAgent] execute failed: Exception {e}")
            return AgentResult(
                status="failed",
                result={},
                error=str(e),
            )


__all__ = ["NoteTakingAgent"]
