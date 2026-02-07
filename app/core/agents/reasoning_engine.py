"""Reasoning engine component using Claude SDK."""

from typing import Any, Dict, List, Optional
from opik import track
from app.utils.opik_wrapper import store_prompt
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    query,
)


class ReasoningEngine:
    """Core reasoning engine using Claude SDK for decision-making."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: Optional[str] = None,
    ):
        """Initialize the reasoning engine.

        Args:
            api_key: Anthropic API key (optional, uses env var if not provided)
            model: Claude model to use
            system_prompt: Optional system prompt
        """
        self.model = model
        self.system_prompt = system_prompt
        self.api_key = api_key
        self._opik_logged_system_prompts: set[str] = set()
        
    
    @track
    async def reason(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        mcp_servers: Optional[Dict[str, Any]] = None,
        max_tokens: int = 4096,
        caller: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform reasoning with Claude.

        Args:
            prompt: Reasoning prompt
            context: Optional context dictionary
            tools: Optional list of allowed tool names
            max_tokens: Maximum tokens in response

        Returns:
            Dictionary with reasoning result and metadata
        """
        # Build full prompt with context
        full_prompt = prompt
        if context:
            context_str = "\n".join(
                f"{k}: {v}" for k, v in context.items()
            )
            full_prompt = f"{prompt}\n\nContext:\n{context_str}"

        # Store prompts in Opik (best-effort)
        caller_name = (
            caller.strip()
            if isinstance(caller, str) and caller.strip()
            else "UnknownCaller"
        )
        system_prompt_name = (
            f"{caller_name}_ReasoningEngine_system_prompt"
        )
        full_prompt_name = f"{caller_name}_ReasoningEngine_full_prompt"

        if self.system_prompt and system_prompt_name not in self._opik_logged_system_prompts:
            store_prompt(
                name=system_prompt_name,
                prompt=self.system_prompt,
                metadata={
                    "component": "ReasoningEngine",
                    "kind": "system_prompt",
                    "caller": caller_name,
                },
            )
            self._opik_logged_system_prompts.add(system_prompt_name)
        store_prompt(
            name=full_prompt_name,
            prompt=full_prompt,
            metadata={
                "component": "ReasoningEngine",
                "kind": "reason",
                "model": self.model,
                "caller": caller_name,
                "has_context": bool(context),
                "has_tools": bool(tools),
                "has_mcp_servers": bool(mcp_servers),
            },
        )

        # Configure Claude agent options (SDK does not accept model/max_tokens in __init__)
        options = ClaudeAgentOptions(
            system_prompt=self.system_prompt or "",
        )

        # Set allowed tools if provided
        if tools:
            options.allowed_tools = tools

        try:
            if mcp_servers:
                options.mcp_servers = mcp_servers
                options.permission_mode = "acceptEdits"
                last_result = None
                last_assistant = None
                async with ClaudeSDKClient(options=options) as client:
                    await client.query(full_prompt)
                    async for message in client.receive_response():
                        if isinstance(message, ResultMessage):
                            last_result = message
                        elif isinstance(message, AssistantMessage):
                            last_assistant = message

                reasoning_result = ""
                if last_result and last_result.result:
                    reasoning_result = last_result.result
                elif last_assistant:
                    reasoning_result = self._extract_assistant_text(
                        last_assistant
                    )

                usage = (
                    getattr(last_result, "usage", {})
                    if last_result
                    else {}
                )
                stop_reason = (
                    getattr(last_result, "stop_reason", None)
                    if last_result
                    else None
                )
            else:
                last_result = None
                last_assistant = None
                async for message in query(
                    prompt=full_prompt, options=options
                ):
                    if isinstance(message, ResultMessage):
                        last_result = message
                    elif isinstance(message, AssistantMessage):
                        last_assistant = message

                reasoning_result = ""
                if last_result and last_result.result:
                    reasoning_result = last_result.result
                elif last_assistant:
                    reasoning_result = self._extract_assistant_text(
                        last_assistant
                    )

                usage = (
                    getattr(last_result, "usage", {})
                    if last_result
                    else {}
                )
                stop_reason = (
                    getattr(last_result, "stop_reason", None)
                    if last_result
                    else None
                )

            return {
                "result": reasoning_result,
                "metadata": {
                    "model": self.model,
                    "usage": usage,
                    "stop_reason": stop_reason,
                },
            }
        except Exception as e:
            return {
                "result": None,
                "error": str(e),
                "metadata": {},
            }

    @staticmethod
    def _extract_assistant_text(message: AssistantMessage) -> str:
        """Extract text content from an AssistantMessage."""
        if isinstance(message.content, str):
            return message.content
        if isinstance(message.content, list):
            text_parts = []
            for item in message.content:
                if isinstance(item, TextBlock):
                    text_parts.append(item.text)
                else:
                    text_parts.append(str(item))
            return "\n".join(text_parts)
        return str(message.content)

    @track
    async def reason_with_json_output(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        caller: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform reasoning and return structured JSON output.

        Args:
            prompt: Reasoning prompt
            context: Optional context dictionary
            schema: Optional JSON schema for output

        Returns:
            Parsed JSON result or error
        """
        # Add JSON output instruction
        json_prompt = f"{prompt}\n\nPlease return your response as valid JSON."
        if schema:
            import json
            schema_str = json.dumps(schema, indent=2)
            json_prompt = (
                f"{json_prompt}\n\nExpected JSON schema:\n{schema_str}"
            )

        caller_name = (
            caller.strip()
            if isinstance(caller, str) and caller.strip()
            else "UnknownCaller"
        )
        store_prompt(
            name=f"{caller_name}_ReasoningEngine_json_prompt",
            prompt=json_prompt,
            metadata={
                "component": "ReasoningEngine",
                "kind": "reason_with_json_output",
                "model": self.model,
                "caller": caller_name,
                "has_context": bool(context),
                "has_schema": bool(schema),
            },
        )

        result = await self.reason(json_prompt, context, caller=caller_name)

        if result.get("error"):
            return result

        # Try to parse JSON from result
        reasoning_text = result.get("result", "")
        try:
            import json
            # Try to extract JSON from the text
            # Look for JSON-like structures
            start_idx = reasoning_text.find("{")
            end_idx = reasoning_text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = reasoning_text[start_idx:end_idx]
                parsed_json = json.loads(json_str)
                return {
                    "result": parsed_json,
                    "metadata": result.get("metadata", {}),
                }
        except Exception:
            pass

        # If JSON parsing fails, return raw result
        return {
            "result": reasoning_text,
            "metadata": result.get("metadata", {}),
            "warning": "Could not parse JSON from response",
        }


__all__ = ["ReasoningEngine"]
