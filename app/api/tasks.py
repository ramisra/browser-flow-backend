import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_types import TaskType
from app.core.tool_registry import ToolRegistry
from app.core.url_actions import run_url_action_agent
from app.db.session import get_async_session
from app.models.user_context import ContextType
from app.repositories.user_context_repository import UserContextRepository
from app.repositories.user_task_repository import UserTaskRepository
from app.models.task_identification import TaskIdentificationResult
from app.services.embedding import EmbeddingService
from app.services.intent_understanding import IntentUnderstandingService
from app.services.parent_topic_mapper import ParentTopicMapper
from app.services.requirement_extractor import RequirementExtractor
from app.services.task_identification import TaskIdentificationService
from app.services.task_executor import TaskExecutor
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.services.task_orchestrator import TaskOrchestrator
from app.services.semantic_knowledge_service import SemanticKnowledgeService
from app.core.agent_registry import AgentRegistry
from app.core.agents.agent_spawner import AgentSpawner
from app.core.tools.excel_tools import ExcelTools


class TaskRequest(BaseModel):
    task_type: Optional[Union[TaskType, str]] = None  # Optional - can be auto-detected
    urls: Optional[List[str]] = None
    selected_text: Optional[str] = None
    user_context: Optional[str] = None

    @field_validator('task_type', mode='before')
    @classmethod
    def validate_task_type(cls, v):
        """Accept both uppercase and lowercase task type values.
        
        Converts input to match the enum values (uppercase).
        """
        # If None, allow it (for auto-detection)
        if v is None:
            return None
            
        # If already a TaskType enum, return as-is
        if isinstance(v, TaskType):
            return v
            
        if isinstance(v, str):
            # Normalize: convert to uppercase and replace hyphens with underscores
            normalized = v.upper().replace('-', '_')
            # Try to find matching enum by value
            for task_type in TaskType:
                if task_type.value == normalized:
                    return task_type
                # Also check enum name
                if task_type.name == normalized:
                    return task_type
            # If not found, raise error with helpful message
            valid_values = ', '.join([f'"{t.value.lower()}"' for t in TaskType])
            raise ValueError(
                f"Invalid task_type: '{v}'. Valid values are: {valid_values}"
            )
        return v

    class Config:
        use_enum_values = False  # We handle conversion manually


class TaskResponse(BaseModel):
    task_id: Optional[str] = None
    task_type: Optional[TaskType] = None
    context_ids: Optional[List[str]] = None
    context_result: Optional[Dict[str, Any]] = None
    actions_result: Optional[Dict[str, Any]] = None
    trello_metadata: Optional[str] = None
    task_identification: Optional[TaskIdentificationResult] = None
    # New fields for intent-to-output orchestration
    detected_intent: Optional[Dict[str, Any]] = None
    workflow_plan: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    execution_status: Optional[str] = None


class TaskListItem(BaseModel):
    """Task item for list view."""

    task_id: str
    task_type: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    user_contexts: List[str]
    timestamp: datetime
    context_count: int = 0

    class Config:
        from_attributes = True


class TasksListResponse(BaseModel):
    """Response for tasks list view."""

    tasks: List[TaskListItem]
    total: int
    page: int
    page_size: int


router = APIRouter(tags=["tasks"])


async def get_user_guest_id(
    x_user_guest_id: Optional[str] = Header(None, alias="X-User-Guest-ID"),
) -> uuid.UUID:
    """Extract and validate user_guest_id from header.

    Args:
        x_user_guest_id: User guest ID from X-User-Guest-ID header

    Returns:
        UUID of the user guest ID

    Raises:
        HTTPException: If header is missing or invalid
    """
    if not x_user_guest_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Guest-ID header is required",
        )

    try:
        return uuid.UUID(x_user_guest_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_guest_id format: {x_user_guest_id}",
        )


async def _execute_task(
    request: TaskRequest,
    user_guest_id: uuid.UUID,
    session: AsyncSession,
    context_result: Optional[Dict[str, Any]],
    context_ids: List[uuid.UUID],
    context_repo: UserContextRepository,
    task_repo: UserTaskRepository,
) -> TaskResponse:
    """Handle automatic intent detection and workflow orchestration.

    Args:
        request: Task request
        user_guest_id: User guest ID
        session: Database session
        context_result: Processed context result
        context_ids: List of context IDs
        context_repo: Context repository
        task_repo: Task repository

    Returns:
        TaskResponse with execution results
    """
    # Get user context text (selected_text or user_context for intent detection)
    user_input = None
    user_task_context = None

    if context_result and isinstance(context_result, dict):
        user_task_context = context_result.get("user_task")
        user_input = context_result.get("selected_text") or context_result.get(
            "user_task"
        )

    if not user_input:
        raise HTTPException(
            status_code=400,
            detail="No context available for intent detection",
        )

    # Initialize orchestration services
    task_identification_service = TaskIdentificationService()
    tool_registry = ToolRegistry()

    # Step 1: Understand intent
    context_metadata = {
        "urls": request.urls or [],
        "tags": [],
    }

    # Identify task type from context
    task_identification = await task_identification_service.identify_task_type(
        user_task_context, context_metadata
    )
    print(f"Task identification: {task_identification}")

    # NEW: Agent system initiation
    execution_result = None
    try:
        # Initialize agent system components
        agent_registry = AgentRegistry()
        tool_registry = ToolRegistry()
        embedding_service = EmbeddingService()
        semantic_knowledge_service = SemanticKnowledgeService(
            embedding_service=embedding_service,
            context_repository=context_repo,
        )
        excel_tools = ExcelTools()
        agent_spawner = AgentSpawner(
            tool_registry=tool_registry,
            embedding_service=None,
            semantic_knowledge_service=semantic_knowledge_service,
            excel_tools=excel_tools,
        )
        task_orchestrator = TaskOrchestrator(
            agent_registry=agent_registry,
            agent_spawner=agent_spawner,
        )

        # Prepare task input combining selected_text and user_context
        task_input = {
            "selected_text": request.selected_text,
            "user_context": request.user_context or user_task_context,
            "urls": request.urls or [],
            "context_result": context_result,
        }

        # Execute agent orchestration
        execution_result = await task_orchestrator.orchestrate_task(
            task_identification=task_identification,
            user_context=user_task_context,
            context_metadata=context_metadata,
            context_result=context_result,
            task_input=task_input,
            user_guest_id=str(user_guest_id),
            context_ids=[str(cid) for cid in context_ids],
        )
        print(f"Agent execution result: {execution_result}")
    except Exception as e:
        print(f"Error in agent orchestration: {e}")
        import traceback
        traceback.print_exc()

    # Step 6: Save task to database
    # Use identified task type for auto-detected tasks
    task_type = task_identification.task_type
    
    output_data = (
        execution_result.agent_results.model_dump()
        if execution_result and hasattr(execution_result, "agent_results")
        else {}
    )

    user_task = await task_repo.create_user_task(
        task_type=task_type,
        user_guest_id=user_guest_id,
        input_data=task_identification.input.model_dump(),
        user_contexts=context_ids,
        output_data=output_data,
    )

    # Update task with intent and workflow plan
    try:
        user_task.execution_status = (
            execution_result.get("status", "PENDING")
            if isinstance(execution_result, dict)
            else (getattr(execution_result, "status", None) or "PENDING")
            if execution_result
            else "PENDING"
        )

        #Flush to ensure fields are saved before commit
        await session.flush()
        await session.commit()
        await session.refresh(user_task)
        
        print(f"Successfully saved task {user_task.task_id} with intent and workflow plan")
    except Exception as e:
        print(f"Error saving intent/workflow fields: {e}")
        # Still commit the task even if intent fields fail
        await session.commit()
        await session.refresh(user_task)  # pyright: ignore[reportUndefinedVariable]

    # Prepare execution result for response
    execution_result_dict = {}
    execution_status = "PENDING"
    if execution_result:
        execution_result_dict = execution_result.model_dump() if hasattr(execution_result, 'model_dump') else execution_result
        execution_status = execution_result.status if hasattr(execution_result, 'status') else "COMPLETED"
    return TaskResponse(
        task_id=str(1),
        task_type=task_type,
        context_ids=[str(cid) for cid in context_ids],
        context_result=context_result,
        task_identification=task_identification,
        execution_result=execution_result_dict,
        execution_status=execution_status,
    )


@router.post("/tasks", response_model=TaskResponse)
async def initiate_task(
    request: TaskRequest,
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
) -> TaskResponse:
    """
    Initiate an agentic task based on task_type.

    - create_action_from_context:
        1) Run the URL context agent over the provided URLs or context.
        2) Run the URL action agent to synthesize next actions from that context.
        3) Save context and task to database.
    - add_to_context:
        1) Run only the URL context agent over the provided URLs or context.
        2) Save context to database.
    """

    if not request.selected_text and not request.user_context and not request.urls:
        raise HTTPException(
            status_code=400,
            detail="At least one of urls, selected_text, or user_context must be provided",
        )

    # Initialize services
    embedding_service = EmbeddingService()
    parent_topic_mapper = ParentTopicMapper(embedding_service)
    context_repo = UserContextRepository(
        session, embedding_service, parent_topic_mapper
    )
    task_repo = UserTaskRepository(session)

    context_ids: List[uuid.UUID] = []
    context_result: Optional[Dict[str, Any]] = None

    # Pre-task context processing: run agent to extract tags, content, etc.
    semantic_knowledge_service = SemanticKnowledgeService(
        embedding_service=embedding_service,
        context_repository=context_repo,
    )
    try:
        if request.urls:
            context_result = await semantic_knowledge_service.process_context(
                urls=request.urls
            )
        else:
            combined = (
                (request.selected_text or "").strip()
                + "\n\n"
                + (request.user_context or "").strip()
            ).strip()
            context_result = await semantic_knowledge_service.process_context(
                context=combined if combined else "No content provided"
            )

        if context_result and context_result.get("contexts"):
            for item in context_result["contexts"]:
                raw_content = (
                    item.get("content") or item.get("short_summary") or ""
                )
                tags = item.get("tags") or []
                uc = await context_repo.create_user_context(
                    raw_content=raw_content,
                    context_tags=tags,
                    user_guest_id=user_guest_id,
                    url=item.get("url"),
                    user_defined_context=item.get("short_summary")
                    or item.get("title"),
                    find_parent=True,
                )
                context_ids.append(uc.context_id)
            await session.flush()
        else:
            context_result = None
    except Exception as e:
        print(f"Context processing failed: {e}")
        context_result = None

    # Fallback: create one minimal user context when processing failed or returned nothing
    if not context_ids:
        fallback_raw = (
            (request.selected_text or "").strip()
            + "\n\n"
            + (request.user_context or "").strip()
        ).strip()
        if not fallback_raw:
            fallback_raw = "User-provided context"
        uc = await context_repo.create_user_context(
            raw_content=fallback_raw,
            context_tags=["user_input"],
            user_guest_id=user_guest_id,
            url=None,
            user_defined_context=None,
            find_parent=True,
        )
        context_ids.append(uc.context_id)
        await session.flush()

    # Pass through for intent/task input (same shape as before)
    context = {
        "user_task": request.user_context,
        "urls": request.urls,
        "selected_text": request.selected_text,
    }

    return await _execute_task(
        request=request,
        user_guest_id=user_guest_id,
        session=session,
        context_result=context,
        context_ids=context_ids,
        context_repo=context_repo,
        task_repo=task_repo,
    )

@router.get("/tasks", response_model=TasksListResponse)
async def get_tasks_list(
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    task_type: Optional[TaskType] = Query(None, description="Filter by task type"),
    search: Optional[str] = Query(None, description="Search in input and output"),
) -> TasksListResponse:
    """
    Get all tasks that the user has asked browser flow to do.

    Supports pagination, filtering by task type, and search in task input/output.
    """
    task_repo = UserTaskRepository(session)

    # Get all tasks for the user
    all_tasks = await task_repo.get_user_tasks_by_guest_id(user_guest_id)

    # Apply filters
    filtered_tasks = all_tasks

    if task_type:
        filtered_tasks = [t for t in filtered_tasks if t.task_type == task_type]

    if search:
        search_lower = search.lower()
        filtered_tasks = [
            t
            for t in filtered_tasks
            if search_lower in str(t.input).lower()
            or search_lower in str(t.output).lower()
            or search_lower in t.task_type.value.lower()
        ]

    # Apply pagination
    total = len(filtered_tasks)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_tasks = filtered_tasks[start:end]

    # Convert to response models
    task_items = [
        TaskListItem(
            task_id=str(t.task_id),
            task_type=t.task_type.value.lower(),  # Convert to lowercase for API
            input=t.input,
            output=t.output,
            user_contexts=[str(cid) for cid in t.user_contexts],
            timestamp=t.timestamp,
            context_count=len(t.user_contexts),
        )
        for t in paginated_tasks
    ]

    return TasksListResponse(
        tasks=task_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
    include_contexts: bool = Query(False, description="Include full context details"),
) -> Dict[str, Any]:
    """
    Get detailed information about a specific task.

    Includes full task information and optionally associated context details.
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task_repo = UserTaskRepository(session)
    task = await task_repo.get_user_task(task_uuid)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify ownership
    if task.user_guest_id != user_guest_id:
        raise HTTPException(status_code=403, detail="Access denied")

    response: Dict[str, Any] = {
        "task_id": str(task.task_id),
        "task_type": task.task_type.value.lower(),  # Convert to lowercase for API
        "input": task.input,
        "output": task.output,
        "user_contexts": [str(cid) for cid in task.user_contexts],
        "timestamp": task.timestamp,
        "context_count": len(task.user_contexts),
    }

    # Optionally include full context details
    if include_contexts and task.user_contexts:
        context_repo = UserContextRepository(
            session,
            EmbeddingService(),
            ParentTopicMapper(EmbeddingService()),
        )
        contexts = await context_repo.get_user_contexts_by_ids(task.user_contexts)
        response["contexts"] = [
            {
                "context_id": str(c.context_id),
                "url": c.url,
                "tags": c.context_tags,
                "content_preview": (
                    c.raw_content[:200] + "..."
                    if len(c.raw_content) > 200
                    else c.raw_content
                ),
                "context_type": c.context_type.value.lower(),  # Convert to lowercase for API
                "timestamp": c.timestamp,
            }
            for c in contexts
        ]

    return response


@router.get("/tasks/{task_id}/excel")
async def download_excel_file(
    task_id: str,
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Download Excel file generated for a task.

    Returns the Excel file if it exists in the task output.
    """
    from fastapi.responses import FileResponse
    from pathlib import Path

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task_repo = UserTaskRepository(session)
    task = await task_repo.get_user_task(task_uuid)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify ownership
    if task.user_guest_id != user_guest_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get Excel file path from output
    output = task.output or {}
    excel_file_path = output.get("excel_file_path")
    
    # Also check execution_result
    if not excel_file_path and "execution_result" in output:
        execution_result = output.get("execution_result", {})
        if isinstance(execution_result, dict):
            excel_file_path = execution_result.get("result", {}).get("excel_file_path")

    if not excel_file_path:
        raise HTTPException(
            status_code=404, detail="No Excel file found for this task"
        )

    # Check if file exists
    file_path = Path(excel_file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Excel file not found on server"
        )

    # Return file
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


__all__ = ["router", "TaskRequest", "TaskResponse"]

