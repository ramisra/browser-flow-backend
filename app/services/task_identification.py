"""Task identification service using Claude agent."""

import json
from typing import Any, Dict, List, Optional

from opik import track
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query

from app.core.task_types import TaskType
from app.models.task_identification import (
    TaskIdentificationMetadata,
    TaskIdentificationResult,
)
from app.utils.opik_wrapper import store_prompt


class TaskIdentificationService:
    """Service for identifying task type from user context."""

    @track
    async def identify_task_type(
        self,
        user_context: str,
        context_metadata: Optional[Dict[str, Any]] = None,
        caller: Optional[str] = None,
    ) -> TaskIdentificationResult:
        """Analyze user context and map it to a TaskType.

        Args:
            user_context: User context text to analyze
            context_metadata: Optional metadata about the context (urls, tags, etc.)

        Returns:
            TaskIdentificationResult with task type and confidence
        """
        context_info = user_context or ""
        if context_metadata:
            urls = context_metadata.get("urls")
            if urls:
                context_info += f"\n\nURLs: {', '.join(str(u) for u in urls)}"
            tags = context_metadata.get("tags")
            if tags:
                context_info += f"\n\nTags: {', '.join(str(t) for t in tags)}"

        task_types_list = "\n".join([f"- {t.value}" for t in TaskType])
        print(f"Task types list: {task_types_list}")
        print(f"Context info: {context_info}")
        prompt = f"""
You are a task identification expert. Analyze the following user context and map it to the most appropriate TaskType.

User Context:
{context_info}

Your task is to:
1. Select exactly one TaskType from the list below
2. Provide a confidence score (0.0 to 1.0)
3. Explain why the task type fits the context
4. Provide up to 3 alternative TaskTypes (lower confidence) if applicable
5. Identify the INPUT parameters required for this task (extract from context as a structured dictionary with key-value pairs)
6. Identify the OUTPUT structure expected from this task (describe what the task should produce as a structured dictionary with key-value pairs)

TaskType list:
{task_types_list}

Return your analysis as a JSON object with this exact structure:
{{
  "task_type": "ONE_TASK_TYPE_FROM_LIST",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "alternative_types": ["TYPE1", "TYPE2"],
  "input": {{
    "key1": "value1",
    "key2": "value2"
  }},
  "output": {{
    "key1": "description of expected value",
    "key2": "description of expected value"
  }}
}}

For INPUT: Extract all parameters, data, or information needed to execute the task from the user context. Use clear, descriptive keys and actual values or descriptions from the context.

For OUTPUT: Describe what the task should produce or return. Use clear, descriptive keys and describe the expected structure/format of each output value.

"""

        system_prompt = (
            "You identify task types accurately from context and return "
            "valid JSON responses matching the requested schema. "
            "Always extract structured input parameters and expected output "
            "from the user context as dictionary objects with clear key-value pairs."
        )

        # caller_name = (
        #     caller.strip()
        #     if isinstance(caller, str) and caller.strip()
        #     else self.__class__.__name__
        # )
        store_prompt(
            name=f"TaskIdentificationService_identify_task_type_system_prompt",
            prompt=system_prompt,
            metadata={
                "component": "TaskIdentificationService",
                "method": "identify_task_type",
                "kind": "system_prompt"
            },
        )
        store_prompt(
            name=f"TaskIdentificationService_identify_task_type_full_prompt",
            prompt=prompt,
            metadata={
                "component": "TaskIdentificationService",
                "method": "identify_task_type",
                "kind": "full_prompt",
                "has_context_metadata": bool(context_metadata),
            },
        )

        final_result: Optional[Dict[str, Any]] = None
        raw_response: Optional[Dict[str, Any]] = None
        accumulated_content: str = ""

        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Edit", "Glob"],
                permission_mode="acceptEdits",
                system_prompt=system_prompt,
            ),
        ):
            print(f"Message: {message}")
            if isinstance(message, AssistantMessage):
                # Extract text content from AssistantMessage blocks
                for block in message.content:
                    if hasattr(block, "text") and block.text:
                        accumulated_content += block.text
                        print(f"Accumulated content: {accumulated_content}")
            elif isinstance(message, ResultMessage):
                # ResultMessage signals completion - try to parse accumulated content
                print(f"ResultMessage received, accumulated content length: {len(accumulated_content)}")
                if accumulated_content:
                    try:
                        final_result = json.loads(accumulated_content)
                        print(f"Final result: {final_result}")
                        raw_response = final_result
                        print(f"Raw response: {raw_response}")
                    except json.JSONDecodeError:
                        import re

                        json_match = re.search(r"\{.*\}", accumulated_content, re.DOTALL)
                        if json_match:
                            try:
                                final_result = json.loads(json_match.group())
                                raw_response = final_result
                                print(f"Parsed JSON from regex match: {final_result}")
                            except json.JSONDecodeError:
                                print(f"Failed to parse JSON from: {accumulated_content}")
                                pass

        if not final_result:
            return TaskIdentificationResult(
                task_type=TaskType.ADD_TO_KNOWLEDGE_BASE,
                confidence=0.5,
                reasoning="Unable to determine task type from context",
                alternative_types=[],
                input=None,
                output=None,
                metadata=TaskIdentificationMetadata(
                    model="claude_agent_sdk", raw_response=raw_response
                ),
            )

        task_type = self._parse_task_type(final_result.get("task_type"))
        alternative_types = self._parse_alternative_types(
            final_result.get("alternative_types", [])
        )
        
        # Extract input and output, ensuring they are dictionaries
        input_data = final_result.get("input")
        if input_data is not None and not isinstance(input_data, dict):
            input_data = None
            
        output_data = final_result.get("output")
        if output_data is not None and not isinstance(output_data, dict):
            output_data = None

        return TaskIdentificationResult(
            task_type=task_type,
            confidence=float(final_result.get("confidence", 0.5)),
            reasoning=final_result.get("reasoning", "Task type analysis"),
            alternative_types=alternative_types,
            input=input_data,
            output=output_data,
            metadata=TaskIdentificationMetadata(
                model="claude_agent_sdk", raw_response=raw_response
            ),
        )

    def _parse_task_type(self, value: Optional[str]) -> TaskType:
        """Parse a TaskType from a string value."""
        if not value:
            return TaskType.ADD_TO_KNOWLEDGE_BASE

        normalized = value.upper().replace("-", "_")
        for task_type in TaskType:
            if task_type.value == normalized or task_type.name == normalized:
                return task_type

        return TaskType.ADD_TO_KNOWLEDGE_BASE

    def _parse_alternative_types(self, values: Any) -> List[TaskType]:
        """Parse alternative task types from raw values."""
        if not isinstance(values, list):
            return []

        alternatives: List[TaskType] = []
        for value in values:
            if not isinstance(value, str):
                continue
            parsed = self._parse_task_type(value)
            if parsed != TaskType.ADD_TO_KNOWLEDGE_BASE and parsed not in alternatives:
                alternatives.append(parsed)

        return alternatives


__all__ = ["TaskIdentificationService"]
