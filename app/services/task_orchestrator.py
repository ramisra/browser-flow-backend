"""Task orchestrator for coordinating task execution."""

from typing import Any, Dict, List, Optional

from app.core.agent_registry import AgentRegistry
from app.core.agents.agent_context import AgentContext
from app.core.agents.agent_communication import AgentCommunicationProtocol
from app.core.agents.agent_spawner import AgentSpawner
from app.models.agent_result import AgentResult, TaskExecutionResult
from app.models.task_identification import TaskIdentificationResult


class TaskOrchestrator:
    """Orchestrates task execution with agent coordination.

    Initiation Point: Called after TaskIdentificationService in tasks.py
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        agent_spawner: AgentSpawner,
        communication_protocol: Optional[AgentCommunicationProtocol] = None,
    ):
        """Initialize the task orchestrator.

        Args:
            agent_registry: Agent registry instance
            agent_spawner: Agent spawner instance
            communication_protocol: Optional communication protocol for multi-agent tasks
        """
        self.agent_registry = agent_registry
        self.agent_spawner = agent_spawner
        self.communication_protocol = (
            communication_protocol or AgentCommunicationProtocol()
        )

    async def orchestrate_task(
        self,
        task_identification: TaskIdentificationResult,
        user_context: str,
        context_metadata: Dict[str, Any],
        context_result: Optional[Dict[str, Any]] = None,
        task_input: Optional[Dict[str, Any]] = None,
        user_guest_id: Optional[str] = None,
        context_ids: Optional[List[str]] = None,
    ) -> TaskExecutionResult:
        """Determine if atomic or non-atomic and coordinate execution.

        Args:
            task_identification: Result from TaskIdentificationService (already called)
            user_context: User context text
            context_metadata: Context metadata (urls, tags, etc.)
            context_result: Processed context result if available
            task_input: Optional task input dictionary
            user_guest_id: Optional user guest ID
            context_ids: Optional list of context IDs

        Returns:
            TaskExecutionResult with agent execution results
        """
        # Check if task is atomic based on task_identification
        if self._is_atomic_task(task_identification):
            return await self._execute_atomic_task(
                task_identification,
                user_context,
                context_metadata,
                context_result,
                task_input,
                user_guest_id,
                context_ids,
            )
        else:
            return await self._execute_non_atomic_task(
                task_identification,
                user_context,
                context_metadata,
                context_result,
                task_input,
                user_guest_id,
                context_ids,
            )

    def _is_atomic_task(
        self, task_identification: TaskIdentificationResult
    ) -> bool:
        """Determine if task is atomic (single agent) or non-atomic (multi-agent).

        Args:
            task_identification: Task identification result

        Returns:
            True if atomic, False if non-atomic
        """
        # For now, most tasks are atomic
        # Non-atomic tasks would require workflow planning
        # This can be enhanced based on task complexity or explicit flags
        return True

    async def _execute_atomic_task(
        self,
        task_identification: TaskIdentificationResult,
        user_context: str,
        context_metadata: Dict[str, Any],
        context_result: Optional[Dict[str, Any]],
        task_input: Optional[Dict[str, Any]],
        user_guest_id: Optional[str],
        context_ids: Optional[List[str]],
    ) -> TaskExecutionResult:
        """Execute single agent for atomic task.

        Uses task_identification.task_type to find appropriate agent from registry.
        """
        # Get agent class from registry based on task_type
        agent_lookup = self.agent_registry.get_agent_class_and_metadata(
            task_identification.task_type
        )
        if not agent_lookup:
            return TaskExecutionResult(
                status="failed",
                result={
                    "error": f"No agent found for task type: {task_identification.task_type}"
                },
            )
        agent_class, agent_metadata = agent_lookup
        print(f"Agent class: {agent_class}")

        # Create agent context
        agent_context = AgentContext(
            user_context=user_context,
            task_identification=task_identification,
            context_metadata=context_metadata,
            context_result=context_result,
            user_guest_id=user_guest_id,
            context_ids=context_ids or [],
        )
        print(f"Agent context: {agent_context}")
        # Spawn agent with context
        agent = await self.agent_spawner.spawn_agent(
            agent_class=agent_class,
            agent_context=agent_context,
            agent_metadata=agent_metadata,
        )
        print(f"Agent: {agent}")
        # Prepare task input
        agent_input = task_input or {}
        # Merge task_identification.input if available
        if task_identification.input:
            agent_input = {**agent_input, **task_identification.input}
        print(f"Agent input: {agent_input}")
        # Execute agent
        try:
            result = await agent.execute(agent_input, agent_context)
            print(f"Agent result: {result}")
            return TaskExecutionResult(
                status="completed",
                result=result.model_dump() if hasattr(result, "model_dump") else result,
                agent_results=[result] if isinstance(result, AgentResult) else [],
            )
        except Exception as e:
            return TaskExecutionResult(
                status="failed",
                result={"error": str(e)},
            )

    async def _execute_non_atomic_task(
        self,
        task_identification: TaskIdentificationResult,
        user_context: str,
        context_metadata: Dict[str, Any],
        context_result: Optional[Dict[str, Any]],
        task_input: Optional[Dict[str, Any]],
        user_guest_id: Optional[str],
        context_ids: Optional[List[str]],
    ) -> TaskExecutionResult:
        """Coordinate multiple agents for non-atomic task.

        Creates workflow plan, spawns multiple agents, coordinates via communication protocol.
        """
        # Create workflow plan based on task_identification
        workflow_plan = await self._create_workflow_plan(task_identification)

        # Create agent context
        agent_context = AgentContext(
            user_context=user_context,
            task_identification=task_identification,
            context_metadata=context_metadata,
            context_result=context_result,
            user_guest_id=user_guest_id,
            context_ids=context_ids or [],
        )

        # Spawn agents for each workflow step
        agents = []
        for step in workflow_plan.get("steps", []):
            agent_lookup = self.agent_registry.get_agent_class_and_metadata(
                step.get("task_type")
            )
            if agent_lookup:
                agent_class, agent_metadata = agent_lookup
                agent = await self.agent_spawner.spawn_agent(
                    agent_class=agent_class,
                    agent_context=agent_context,
                    agent_metadata=agent_metadata,
                )
                agents.append((agent, step))

        # Coordinate execution via communication protocol
        results = await self._coordinate_agents(agents, workflow_plan)

        # Aggregate results
        return TaskExecutionResult(
            status="completed",
            result=results,
            workflow_plan=workflow_plan,
        )

    async def _create_workflow_plan(
        self, task_identification: TaskIdentificationResult
    ) -> Dict[str, Any]:
        """Create workflow plan for non-atomic task.

        Args:
            task_identification: Task identification result

        Returns:
            Workflow plan dictionary
        """
        # Placeholder for workflow planning logic
        # This would analyze task complexity and create a multi-step plan
        return {
            "steps": [],
            "dependencies": {},
        }

    async def _coordinate_agents(
        self, agents: List[tuple], workflow_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Coordinate execution of multiple agents.

        Args:
            agents: List of (agent, step) tuples
            workflow_plan: Workflow plan dictionary

        Returns:
            Aggregated results dictionary
        """
        # Placeholder for multi-agent coordination
        # This would handle dependencies, parallel execution, etc.
        results = []
        for agent, step in agents:
            try:
                result = await agent.execute(step.get("input", {}))
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})

        return {"agent_results": results}


__all__ = ["TaskOrchestrator"]
