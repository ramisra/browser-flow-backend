"""Task execution service for running workflows."""

from typing import Any, Dict, List, Optional

from app.core.composio_trello import create_trello_task_from_actions_result
from app.core.tool_registry import ToolRegistry
from app.core.url_context import run_url_context_agent
from app.models.workflow_plan import ExecutionMode, StepStatus, WorkflowPlan, WorkflowStep


class TaskExecutor:
    """Service for executing workflow plans."""

    def __init__(self, tool_registry: ToolRegistry):
        """Initialize the task executor.

        Args:
            tool_registry: Tool registry instance
        """
        self.tool_registry = tool_registry

    async def execute_workflow(
        self, plan: WorkflowPlan, context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a workflow plan.

        Args:
            plan: Workflow plan to execute
            context_data: Optional context data to use during execution

        Returns:
            Execution results with outputs from each step
        """
        results: Dict[str, Any] = {
            "plan_id": plan.plan_id,
            "steps": [],
            "status": "in_progress",
            "outputs": {},
            "errors": [],
        }

        context_data = context_data or {}

        # Track completed steps for dependency resolution
        completed_steps: Dict[str, Any] = {}

        # Execute steps in order, respecting dependencies
        for step in plan.steps:
            # Check if dependencies are met
            if not self._dependencies_met(step, completed_steps):
                step.status = StepStatus.SKIPPED
                step.error = "Dependencies not met"
                results["steps"].append(self._step_to_dict(step))
                continue

            # Execute the step
            step.status = StepStatus.IN_PROGRESS
            try:
                step_result = await self._execute_step(step, completed_steps, context_data)
                step.status = StepStatus.COMPLETED
                step.result = step_result
                completed_steps[step.step_id] = step_result
                results["outputs"][step.step_id] = step_result
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                results["errors"].append(
                    {"step_id": step.step_id, "error": str(e)}
                )
                # Decide whether to continue or stop
                # For now, continue with other steps

            results["steps"].append(self._step_to_dict(step))

        # Determine final status
        if any(s["status"] == "FAILED" for s in results["steps"]):
            results["status"] = "partial_success" if results["outputs"] else "failed"
        elif all(s["status"] in ["COMPLETED", "SKIPPED"] for s in results["steps"]):
            results["status"] = "completed"
        else:
            results["status"] = "in_progress"

        return results

    def _dependencies_met(
        self, step: WorkflowStep, completed_steps: Dict[str, Any]
    ) -> bool:
        """Check if all dependencies for a step are met.

        Args:
            step: Workflow step
            completed_steps: Dictionary of completed step results

        Returns:
            True if all dependencies are met
        """
        if not step.dependencies:
            return True

        return all(dep_id in completed_steps for dep_id in step.dependencies)

    async def _execute_step(
        self,
        step: WorkflowStep,
        completed_steps: Dict[str, Any],
        context_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single workflow step.

        Args:
            step: Workflow step to execute
            completed_steps: Results from previous steps
            context_data: Context data

        Returns:
            Step execution result
        """
        # Resolve parameter values (may reference previous steps)
        resolved_params = self._resolve_parameters(
            step.tool_params, completed_steps, context_data
        )

        # Execute based on tool name
        if step.tool_name == "trello_create_card":
            return await self._execute_trello_create_card(resolved_params)
        elif step.tool_name == "trello_create_list":
            return await self._execute_trello_create_list(resolved_params)
        elif step.tool_name == "google_sheets_append":
            return await self._execute_google_sheets_append(resolved_params)
        elif step.tool_name == "save_to_context":
            return await self._execute_save_to_context(resolved_params, context_data)
        elif step.tool_name == "web_fetch":
            return await self._execute_web_fetch(resolved_params)
        else:
            # Unknown tool - try to handle generically
            return {
                "status": "unknown_tool",
                "tool_name": step.tool_name,
                "params": resolved_params,
                "message": f"Tool {step.tool_name} not implemented",
            }

    def _resolve_parameters(
        self,
        params: Dict[str, Any],
        completed_steps: Dict[str, Any],
        context_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolve parameter values, including references to previous steps.

        Args:
            params: Original parameters
            completed_steps: Results from previous steps
            context_data: Context data

        Returns:
            Resolved parameters
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # Reference to previous step: $step_id.field
                ref_parts = value[1:].split(".")
                if len(ref_parts) == 2:
                    step_id, field = ref_parts
                    if step_id in completed_steps:
                        resolved[key] = completed_steps[step_id].get(field, value)
                    else:
                        resolved[key] = value
                else:
                    resolved[key] = value
            elif isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                # Template variable: {{context.field}}
                var_name = value[2:-2].strip()
                if var_name.startswith("context."):
                    field = var_name.split(".", 1)[1]
                    resolved[key] = context_data.get(field, value)
                else:
                    resolved[key] = value
            else:
                resolved[key] = value

        return resolved

    async def _execute_trello_create_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Trello card creation.

        Args:
            params: Tool parameters

        Returns:
            Execution result
        """
        # Use the existing Composio integration
        # Format the params to match what create_trello_task_from_actions_result expects
        actions_result = {
            "tasks": [
                {
                    "title": params.get("card_title", "Task"),
                    "reason": params.get("card_description", ""),
                    "subtasks": params.get("checklist_items", []),
                }
            ]
        }

        try:
            await create_trello_task_from_actions_result(actions_result)
            return {
                "status": "success",
                "message": "Trello card created successfully",
                "board": params.get("board_name"),
                "list": params.get("list_name"),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def _execute_trello_create_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Trello list creation.

        Args:
            params: Tool parameters

        Returns:
            Execution result
        """
        # This would need Composio integration for list creation
        # For now, return a placeholder
        return {
            "status": "not_implemented",
            "message": "Trello list creation not yet implemented",
            "params": params,
        }

    async def _execute_google_sheets_append(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Sheets append.

        Args:
            params: Tool parameters

        Returns:
            Execution result
        """
        # This would need Composio Google Sheets integration
        # For now, return a placeholder
        return {
            "status": "not_implemented",
            "message": "Google Sheets append not yet implemented",
            "params": params,
        }

    async def _execute_save_to_context(
        self, params: Dict[str, Any], context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute save to context.

        Args:
            params: Tool parameters
            context_data: Context data

        Returns:
            Execution result
        """
        # This would integrate with the context repository
        # For now, return a placeholder
        return {
            "status": "success",
            "message": "Context saved (placeholder)",
            "content": params.get("content", ""),
        }

    async def _execute_web_fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web fetch.

        Args:
            params: Tool parameters

        Returns:
            Execution result
        """
        url = params.get("url")
        if not url:
            return {
                "status": "error",
                "error": "URL parameter required",
            }

        try:
            # Use existing URL context agent
            result = await run_url_context_agent(urls=[url])
            return {
                "status": "success",
                "url": url,
                "content": result,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    def _step_to_dict(self, step: WorkflowStep) -> Dict[str, Any]:
        """Convert workflow step to dictionary.

        Args:
            step: Workflow step

        Returns:
            Dictionary representation
        """
        return {
            "step_id": step.step_id,
            "tool_name": step.tool_name,
            "status": step.status.value,
            "result": step.result,
            "error": step.error,
        }


__all__ = ["TaskExecutor"]
