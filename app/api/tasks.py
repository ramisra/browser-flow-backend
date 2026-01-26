import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.composio_trello import create_trello_task_from_actions_result
from app.core.task_types import TaskType
from app.core.tool_registry import ToolRegistry
from app.core.url_actions import run_url_action_agent
from app.core.url_context import run_url_context_agent
from app.db.session import get_async_session
from app.models.user_context import ContextType
from app.repositories.user_context_repository import UserContextRepository
from app.repositories.user_task_repository import UserTaskRepository
from app.services.embedding import EmbeddingService
from app.services.intent_understanding import IntentUnderstandingService
from app.services.parent_topic_mapper import ParentTopicMapper
from app.services.requirement_extractor import RequirementExtractor
from app.services.task_executor import TaskExecutor
from app.services.workflow_orchestrator import WorkflowOrchestrator


class TaskRequest(BaseModel):
    task_type: Optional[Union[TaskType, str]] = None  # Optional - can be auto-detected
    urls: Optional[List[str]] = None
    selected_text: Optional[str] = None
    user_context: Optional[str] = None
    workflow_tools: Optional[List[str]] = None
    auto_detect_intent: bool = True  # Enable automatic intent detection

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


async def _handle_auto_intent_detection(
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
    # Get user context text
    user_context_text = request.user_context or request.selected_text or ""
    
    # Extract context from context_result if available
    if context_result and isinstance(context_result, dict):
        if "contexts" in context_result:
            # Combine all context content
            contexts = context_result.get("contexts", [])
            if contexts:
                user_context_text = "\n\n".join([
                    ctx.get("content", ctx.get("raw_content", ""))
                    for ctx in contexts
                    if isinstance(ctx, dict)
                ])
        elif "content" in context_result:
            user_context_text = context_result.get("content", user_context_text)

    if not user_context_text:
        raise HTTPException(
            status_code=400,
            detail="No context available for intent detection",
        )

    # Initialize orchestration services
    intent_service = IntentUnderstandingService()
    requirement_extractor = RequirementExtractor()
    tool_registry = ToolRegistry()
    workflow_orchestrator = WorkflowOrchestrator(tool_registry)
    task_executor = TaskExecutor(tool_registry)

    # Step 1: Understand intent
    context_metadata = {
        "urls": request.urls or [],
        "tags": [],
    }
    if context_result and isinstance(context_result, dict):
        if "contexts" in context_result:
            contexts = context_result.get("contexts", [])
            if contexts:
                context_metadata["tags"] = contexts[0].get("tags", [])

    intent = await intent_service.understand_intent(
        user_context_text, context_metadata
    )

    # Step 2: Extract requirements
    requirements = await requirement_extractor.extract_requirements(
        user_context_text, intent, context_metadata
    )

    # Step 3: Create workflow plan
    workflow_plan = await workflow_orchestrator.create_workflow_plan(
        intent, requirements, user_context_text
    )

    # Step 4: Execute workflow
    context_data = {
        "user_context": user_context_text,
        "urls": request.urls or [],
        "intent": intent.model_dump(),
        "requirements": requirements.model_dump(),
    }
    execution_result = await task_executor.execute_workflow(
        workflow_plan, context_data
    )

    # Step 5: Prepare task data
    input_data: Dict[str, Any] = {
        "workflow_tools": request.workflow_tools or [],
        "user_context": user_context_text,
        "urls": request.urls or [],
        "auto_detected": True,
    }

    output_data: Dict[str, Any] = {
        "execution_result": execution_result,
        "response_tokens": str(execution_result),
        "response_file": "",
        "response_image": "",
    }

    # Step 6: Save task to database
    # Use ADD_TO_CONTEXT as default task type for auto-detected tasks
    task_type = request.task_type or TaskType.ADD_TO_CONTEXT
    
    user_task = await task_repo.create_user_task(
        task_type=task_type,
        user_guest_id=user_guest_id,
        input_data=input_data,
        user_contexts=context_ids,
        output_data=output_data,
    )

    # Update task with intent and workflow plan
    try:
        user_task.detected_intent = intent.model_dump()
        user_task.workflow_plan = workflow_plan.model_dump()
        user_task.execution_status = execution_result.get("status", "PENDING")

        # Flush to ensure fields are saved before commit
        await session.flush()
        await session.commit()
        await session.refresh(user_task)
        
        print(f"Successfully saved task {user_task.task_id} with intent and workflow plan")
    except Exception as e:
        print(f"Error saving intent/workflow fields: {e}")
        # Still commit the task even if intent fields fail
        await session.commit()
        await session.refresh(user_task)

    return TaskResponse(
        task_id=str(user_task.task_id),
        task_type=task_type,
        context_ids=[str(cid) for cid in context_ids],
        context_result=context_result,
        detected_intent=intent.model_dump(),
        workflow_plan=workflow_plan.model_dump(),
        execution_result=execution_result,
        execution_status=execution_result.get("status", "PENDING"),
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

    if not request.selected_text and not request.urls:
        raise HTTPException(
            status_code=400, detail="Either urls or context must be provided"
        )

    # Initialize services
    embedding_service = EmbeddingService()
    parent_topic_mapper = ParentTopicMapper(embedding_service)
    context_repo = UserContextRepository(
        session, embedding_service, parent_topic_mapper
    )
    task_repo = UserTaskRepository(session)

    context_ids: List[uuid.UUID] = []

    # Process context
    context_result = await run_url_context_agent(
        urls=request.urls, context=request.selected_text or request.user_context
    )

    # Save context(s) to database
    if context_result:
        # The context_result should now be a dict with "contexts" key containing a list
        # Each context has: url, title, tags, content, short_summary
        contexts_to_save = []
        
        if isinstance(context_result, dict):
            # Check if it's the new format with "contexts" key
            if "contexts" in context_result:
                contexts_to_save = context_result["contexts"]
            # Fallback: if it's a single context object
            elif "content" in context_result or "tags" in context_result:
                contexts_to_save = [context_result]
        elif isinstance(context_result, list):
            # If it's already a list
            contexts_to_save = context_result

        # Process each context and save to database
        for ctx in contexts_to_save:
            if not isinstance(ctx, dict):
                continue
                
            url = ctx.get("url")
            tags = ctx.get("tags", [])
            content = ctx.get("content") or ctx.get("raw_content", "")
            user_defined_context = ctx.get("short_summary") or ctx.get("title")
            
            # Skip if no content
            if not content:
                continue

            # Determine context type (simplified - could be enhanced)
            context_type = ContextType.TEXT
            if url:
                url_lower = url.lower()
                if any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]):
                    context_type = ContextType.IMAGE
                elif any(ext in url_lower for ext in [".mp4", ".avi", ".mov", ".webm"]):
                    context_type = ContextType.VIDEO

            try:
                # Create user context in database
                user_context = await context_repo.create_user_context(
                    raw_content=content,
                    context_tags=tags,
                    user_guest_id=user_guest_id,
                    url=url,
                    user_defined_context=user_defined_context,
                    context_type=context_type,
                    find_parent=True,
                )
                context_ids.append(user_context.context_id)
            except Exception as e:
                print(f"Error saving context to database: {e}")
                # Rollback the session to clear any pending transaction state
                await session.rollback()
                # Continue with other contexts even if one fails
                continue

        # Commit all contexts at once
        if context_ids:
            try:
                await session.commit()
                print(f"Successfully saved {len(context_ids)} context(s) to database")
            except Exception as e:
                print(f"Error committing contexts to database: {e}")
                await session.rollback()

    # Handle automatic intent detection if enabled or task_type is not provided
    if request.auto_detect_intent or request.task_type is None:
        return await _handle_auto_intent_detection(
            request=request,
            user_guest_id=user_guest_id,
            session=session,
            context_result=request.selected_text or request.user_context,
            context_ids=context_ids,
            context_repo=context_repo,
            task_repo=task_repo,
        )

    # Handle different task types
    if request.task_type == TaskType.ADD_TO_CONTEXT:
        # Create task record for add_to_context as well
        input_data: Dict[str, Any] = {
            "workflow_tools": request.workflow_tools or [],
            "user_context": request.user_context or request.selected_text or "",
            "urls": request.urls or [],
        }
        
        output_data: Dict[str, Any] = {
            "response_tokens": "",
            "response_file": "",
            "response_image": "",
        }
        
        # Create task in database
        user_task = await task_repo.create_user_task(
            task_type=request.task_type,
            user_guest_id=user_guest_id,
            input_data=input_data,
            user_contexts=context_ids,
            output_data=output_data,
        )
        
        # Commit task
        await session.commit()
        
        return TaskResponse(
            task_id=str(user_task.task_id),
            task_type=request.task_type,
            context_ids=[str(cid) for cid in context_ids],
            context_result=context_result,
        )

    if request.task_type == TaskType.CREATE_ACTION_FROM_CONTEXT:
        actions_result = await run_url_action_agent(context=context_result)

        # Invoke Composio/Trello integration using the first task and its subtasks.
        trello_metadata = ""
        if actions_result:
            try:
                await create_trello_task_from_actions_result(actions_result)
                trello_metadata = "Trello task created successfully"
            except Exception as e:
                trello_metadata = f"Trello task creation failed: {str(e)}"

        # Prepare input data
        input_data: Dict[str, Any] = {
            "workflow_tools": request.workflow_tools or [],
            "user_context": request.user_context or request.selected_text or "",
        }

        # Prepare output data
        output_data: Dict[str, Any] = {
            "response_tokens": str(actions_result) if actions_result else "",
            "response_file": "",
            "response_image": "",
        }

        # Create task in database
        user_task = await task_repo.create_user_task(
            task_type=request.task_type,
            user_guest_id=user_guest_id,
            input_data=input_data,
            user_contexts=context_ids,
            output_data=output_data,
        )

        # Commit task
        await session.commit()

        return TaskResponse(
            task_id=str(user_task.task_id),
            task_type=request.task_type,
            context_ids=[str(cid) for cid in context_ids],
            context_result=context_result,
            actions_result=actions_result,
            trello_metadata=trello_metadata,
        )

    # This should be unreachable due to the enum type, but kept as a safeguard.
    raise HTTPException(
        status_code=400, detail=f"Unsupported task_type: {request.task_type.value}"
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


__all__ = ["router", "TaskRequest", "TaskResponse"]

