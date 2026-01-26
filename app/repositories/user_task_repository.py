"""Repository for UserTask database operations."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_types import TaskType
from app.models.user_task import UserTask


class UserTaskRepository:
    """Repository for UserTask CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the repository.

        Args:
            session: Database session
        """
        self.session = session

    async def create_user_task(
        self,
        task_type: TaskType,
        user_guest_id: uuid.UUID,
        input_data: Dict[str, Any],
        user_contexts: List[uuid.UUID],
        output_data: Optional[Dict[str, Any]] = None,
    ) -> UserTask:
        """Create a new user task.

        Args:
            task_type: Type of task
            user_guest_id: User identifier
            input_data: Input JSONB data (workflow_tools, user_context, etc.)
            user_contexts: List of context IDs associated with the task
            output_data: Optional output JSONB data (response_tokens, response_file, etc.)

        Returns:
            Created UserTask instance
        """
        user_task = UserTask(
            task_type=task_type,
            input=input_data,
            output=output_data or {},
            user_guest_id=user_guest_id,
            user_contexts=user_contexts,
            timestamp=datetime.utcnow(),
        )

        self.session.add(user_task)
        await self.session.flush()
        await self.session.refresh(user_task)

        return user_task

    async def get_user_task(self, task_id: uuid.UUID) -> Optional[UserTask]:
        """Get a user task by ID.

        Args:
            task_id: Task identifier

        Returns:
            UserTask instance or None if not found
        """
        result = await self.session.execute(
            select(UserTask).where(UserTask.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_user_tasks_by_guest_id(
        self, user_guest_id: uuid.UUID, limit: Optional[int] = None
    ) -> List[UserTask]:
        """Get all user tasks for a guest ID.

        Args:
            user_guest_id: User identifier
            limit: Optional limit on number of results

        Returns:
            List of UserTask instances
        """
        query = (
            select(UserTask)
            .where(UserTask.user_guest_id == user_guest_id)
            .order_by(UserTask.timestamp.desc())
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_task_output(
        self, task_id: uuid.UUID, output_data: Dict[str, Any]
    ) -> Optional[UserTask]:
        """Update the output of a task.

        Args:
            task_id: Task identifier
            output_data: Output JSONB data to update

        Returns:
            Updated UserTask instance or None if not found
        """
        task = await self.get_user_task(task_id)
        if not task:
            return None

        task.output = output_data
        await self.session.flush()
        await self.session.refresh(task)

        return task
