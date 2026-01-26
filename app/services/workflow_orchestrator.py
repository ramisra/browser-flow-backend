"""Workflow orchestration service."""

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from app.core.tool_registry import ToolMetadata, ToolRegistry
from app.models.intent_classification import IntentClassification
from app.models.workflow_plan import ExecutionMode, StepStatus, WorkflowPlan, WorkflowStep
from app.services.requirement_extractor import RequirementSpec


class WorkflowOrchestrator:
    """Service for planning multi-step workflows."""

    def __init__(self, tool_registry: ToolRegistry):
        """Initialize the workflow orchestrator.

        Args:
            tool_registry: Tool registry instance
        """
        self.tool_registry = tool_registry

    async def create_workflow_plan(
        self,
        intent: IntentClassification,
        requirements: RequirementSpec,
        context: str,
    ) -> WorkflowPlan:
        """Create a workflow plan based on intent and requirements.

        Args:
            intent: Classified intent
            requirements: Extracted requirements
            context: Original user context

        Returns:
            WorkflowPlan with ordered steps
        """
        # Discover relevant tools
        tools = self.tool_registry.discover_tools(
            intent.category, intent.keywords, limit=10
        )

        if not tools:
            # Fallback: create a simple plan with available tools
            return self._create_fallback_plan(requirements)

        # Use Claude to plan the workflow
        plan = await self._plan_with_ai(intent, requirements, tools, context)

        return plan

    async def _plan_with_ai(
        self,
        intent: IntentClassification,
        requirements: RequirementSpec,
        tools: List[ToolMetadata],
        context: str,
    ) -> WorkflowPlan:
        """Use AI to plan the workflow.

        Args:
            intent: Classified intent
            requirements: Extracted requirements
            tools: Available tools
            context: Original user context

        Returns:
            WorkflowPlan
        """
        # Build tools description
        tools_description = "\n".join(
            [
                f"- {tool.name}: {tool.description} (capabilities: {', '.join(tool.capabilities)})"
                for tool in tools
            ]
        )

        prompt = f"""
You are a workflow planning expert. Based on the user's intent and requirements, create a detailed execution plan.

User Context:
{context}

Intent:
- Category: {intent.category.value}
- Description: {intent.description}

Requirements:
- Inputs: {requirements.inputs}
- Outputs: {requirements.outputs}
- Constraints: {requirements.constraints}
- Dependencies: {requirements.dependencies}
- Priority: {requirements.priority}
- Complexity: {requirements.estimated_complexity}

Available Tools:
{tools_description}

Your task is to create a workflow plan that:
1. Uses the available tools to fulfill the requirements
2. Handles dependencies between steps
3. Determines execution order (sequential or parallel where possible)
4. Maps requirement inputs to tool parameters
5. Handles the expected outputs

Return your plan as a JSON object with this exact structure:
{{
  "steps": [
    {{
      "step_id": "step_1",
      "tool_name": "tool_name_from_available_tools",
      "tool_params": {{
        "param1": "value or reference to previous step output",
        "param2": "value"
      }},
      "dependencies": [],
      "execution_mode": "SEQUENTIAL",
      "description": "what this step does"
    }},
    {{
      "step_id": "step_2",
      "tool_name": "another_tool",
      "tool_params": {{}},
      "dependencies": ["step_1"],
      "execution_mode": "SEQUENTIAL",
      "description": "what this step does"
    }}
  ],
  "estimated_duration": 30.0,
  "metadata": {{
    "reasoning": "why this plan was chosen"
  }}
}}

Important:
- Use only tools from the available tools list
- Map requirement inputs to tool parameters appropriately
- Handle dependencies correctly (steps that depend on others should list their step_ids)
- Use PARALLEL execution mode only when steps are truly independent
- Be specific with tool parameters - use actual values or references to previous steps
"""

        final_result: Optional[Dict[str, Any]] = None

        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Edit", "Glob"],
                permission_mode="acceptEdits",
                system_prompt=(
                    "You are an expert at planning workflows. "
                    "You create efficient, logical execution plans that fulfill user requirements."
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

        # Parse and create workflow plan
        if not final_result or "steps" not in final_result:
            return self._create_fallback_plan(requirements)

        try:
            steps = []
            for step_data in final_result.get("steps", []):
                step = WorkflowStep(
                    step_id=step_data.get("step_id", f"step_{len(steps) + 1}"),
                    tool_name=step_data.get("tool_name", ""),
                    tool_params=step_data.get("tool_params", {}),
                    dependencies=step_data.get("dependencies", []),
                    status=StepStatus.PENDING,
                    execution_mode=ExecutionMode(
                        step_data.get("execution_mode", "SEQUENTIAL")
                    ),
                )
                steps.append(step)

            return WorkflowPlan(
                plan_id=str(uuid.uuid4()),
                steps=steps,
                estimated_duration=final_result.get("estimated_duration"),
                metadata=final_result.get("metadata", {}),
            )
        except (ValueError, KeyError, TypeError) as e:
            # Fallback on errors
            return self._create_fallback_plan(requirements)

    def _create_fallback_plan(self, requirements: RequirementSpec) -> WorkflowPlan:
        """Create a simple fallback plan.

        Args:
            requirements: Extracted requirements

        Returns:
            Simple WorkflowPlan
        """
        # Create a simple single-step plan
        step = WorkflowStep(
            step_id="step_1",
            tool_name="save_to_context",
            tool_params={"content": "User request processed"},
            dependencies=[],
            status=StepStatus.PENDING,
            execution_mode=ExecutionMode.SEQUENTIAL,
        )

        return WorkflowPlan(
            plan_id=str(uuid.uuid4()),
            steps=[step],
            estimated_duration=5.0,
            metadata={"fallback": True},
        )


__all__ = ["WorkflowOrchestrator"]
