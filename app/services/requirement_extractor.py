"""Requirement extraction service."""

import json
from typing import Any, Dict, List, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)
from pydantic import BaseModel, Field

from app.models.intent_classification import IntentClassification


class RequirementSpec(BaseModel):
    """Structured requirement specification."""

    inputs: Dict[str, Any] = Field(
        default_factory=dict, description="Required input parameters"
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict, description="Expected output format and fields"
    )
    constraints: List[str] = Field(
        default_factory=list, description="Constraints and conditions"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Dependencies between steps"
    )
    priority: str = Field(default="medium", description="Priority level: low, medium, high")
    estimated_complexity: str = Field(
        default="moderate", description="Complexity: simple, moderate, complex"
    )


class RequirementExtractor:
    """Service for extracting structured requirements from user context."""

    async def extract_requirements(
        self,
        context: str,
        intent: IntentClassification,
        context_metadata: Optional[Dict[str, Any]] = None,
    ) -> RequirementSpec:
        """Extract structured requirements from user context.

        Args:
            context: User context text
            intent: Classified intent
            context_metadata: Optional metadata about the context

        Returns:
            RequirementSpec with inputs, outputs, constraints, and dependencies
        """
        context_info = context
        if context_metadata:
            if "urls" in context_metadata:
                context_info += f"\n\nURLs: {', '.join(context_metadata['urls'])}"
            if "tags" in context_metadata:
                context_info += f"\n\nTags: {', '.join(context_metadata['tags'])}"

        prompt = f"""
You are a requirements analysis expert. Based on the user context and identified intent, extract specific, actionable requirements.

User Context:
{context_info}

Identified Intent:
- Category: {intent.category.value}
- Description: {intent.description}
- Keywords: {', '.join(intent.keywords)}

Your task is to extract:
1. **Inputs**: What parameters, data, or information are needed to fulfill this requirement?
   - List specific inputs with their types and descriptions
   - Include any data sources, URLs, or external inputs needed

2. **Outputs**: What should be the expected result or output?
   - Describe the format and structure of the output
   - List specific fields or data that should be included
   - Specify if output should be saved, displayed, or sent somewhere

3. **Constraints**: What are the limitations, conditions, or requirements?
   - Time constraints
   - Format requirements
   - Access restrictions
   - Quality standards

4. **Dependencies**: What steps or prerequisites are needed?
   - Sequential steps that must happen in order
   - Data dependencies
   - External service dependencies

5. **Priority**: How urgent is this? (low, medium, high)

6. **Complexity**: How complex is this task? (simple, moderate, complex)

Return your analysis as a JSON object with this exact structure:
{{
  "inputs": {{
    "param1": "description and type",
    "param2": "description and type"
  }},
  "outputs": {{
    "format": "description of output format",
    "fields": ["field1", "field2"],
    "destination": "where output should go"
  }},
  "constraints": [
    "constraint1",
    "constraint2"
  ],
  "dependencies": [
    "dependency1",
    "dependency2"
  ],
  "priority": "low|medium|high",
  "estimated_complexity": "simple|moderate|complex"
}}

Be specific and actionable. Think about what tools or services would need to accomplish this task.
"""

        final_result: Optional[Dict[str, Any]] = None

        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Edit", "Glob"],
                permission_mode="acceptEdits",
                system_prompt=(
                    "You are an expert at extracting actionable requirements from user context. "
                    "You identify specific inputs, outputs, constraints, and dependencies."
                ),
            ),
        ):
            if isinstance(message, ResultMessage):
                if hasattr(message, "content"):
                    content = message.content
                    if isinstance(content, str):
                        try:
                            final_result = json.loads(content)
                        except json.JSONDecodeError:
                            import re

                            json_match = re.search(r"\{.*\}", content, re.DOTALL)
                            if json_match:
                                try:
                                    final_result = json.loads(json_match.group())
                                except json.JSONDecodeError:
                                    pass
                elif hasattr(message, "text"):
                    try:
                        final_result = json.loads(message.text)
                    except (json.JSONDecodeError, AttributeError):
                        pass

        # Parse and validate the result
        if not final_result:
            return RequirementSpec(
                inputs={},
                outputs={},
                constraints=[],
                dependencies=[],
                priority="medium",
                estimated_complexity="moderate",
            )

        try:
            return RequirementSpec(
                inputs=final_result.get("inputs", {}),
                outputs=final_result.get("outputs", {}),
                constraints=final_result.get("constraints", []),
                dependencies=final_result.get("dependencies", []),
                priority=final_result.get("priority", "medium"),
                estimated_complexity=final_result.get("estimated_complexity", "moderate"),
            )
        except (ValueError, KeyError, TypeError):
            return RequirementSpec(
                inputs={},
                outputs={},
                constraints=[],
                dependencies=[],
                priority="medium",
                estimated_complexity="moderate",
            )


__all__ = ["RequirementExtractor", "RequirementSpec"]
