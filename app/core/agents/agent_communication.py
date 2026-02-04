"""Agent communication protocol for multi-agent collaboration."""

from typing import Any, Dict, List, Optional
from collections import defaultdict
import asyncio

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """Message between agents."""

    from_agent: str = Field(..., description="Sender agent ID")
    to_agent: str = Field(..., description="Receiver agent ID")
    message_type: str = Field(..., description="Message type")
    content: Dict[str, Any] = Field(..., description="Message content")
    timestamp: float = Field(..., description="Message timestamp")


class AgentCommunicationProtocol:
    """Protocol for agent-to-agent communication."""

    def __init__(self):
        """Initialize the communication protocol."""
        self._message_queue: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._shared_context: Dict[str, Any] = {}
        self._message_lock = asyncio.Lock()

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message: Dict[str, Any],
        message_type: str = "data",
    ) -> Dict[str, Any]:
        """Send a message from one agent to another.

        Args:
            from_agent: Sender agent ID
            to_agent: Receiver agent ID
            message: Message content dictionary
            message_type: Type of message

        Returns:
            Acknowledgment dictionary
        """
        import time
        agent_message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=message,
            timestamp=time.time(),
        )

        async with self._message_lock:
            self._message_queue[to_agent].append(agent_message)

        return {
            "status": "sent",
            "to_agent": to_agent,
            "message_type": message_type,
        }

    async def receive_messages(
        self, agent_id: str, clear: bool = True
    ) -> List[AgentMessage]:
        """Receive messages for an agent.

        Args:
            agent_id: Agent ID to receive messages for
            clear: Whether to clear messages after receiving

        Returns:
            List of messages
        """
        async with self._message_lock:
            messages = self._message_queue.get(agent_id, [])
            if clear:
                self._message_queue[agent_id] = []
            return messages

    async def broadcast(
        self, from_agent: str, message: Dict[str, Any], agent_ids: List[str]
    ) -> Dict[str, Any]:
        """Broadcast a message to multiple agents.

        Args:
            from_agent: Sender agent ID
            message: Message content dictionary
            agent_ids: List of recipient agent IDs

        Returns:
            Broadcast acknowledgment
        """
        results = []
        for agent_id in agent_ids:
            result = await self.send_message(
                from_agent, agent_id, message, message_type="broadcast"
            )
            results.append(result)

        return {
            "status": "broadcast",
            "recipients": len(agent_ids),
            "results": results,
        }

    async def get_shared_context(self) -> Dict[str, Any]:
        """Get the shared context.

        Returns:
            Shared context dictionary
        """
        return self._shared_context.copy()

    async def update_shared_context(self, updates: Dict[str, Any]) -> None:
        """Update the shared context.

        Args:
            updates: Dictionary of updates to apply
        """
        async with self._message_lock:
            self._shared_context.update(updates)

    async def wait_for_message(
        self,
        agent_id: str,
        message_type: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """Wait for a message of a specific type.

        Args:
            agent_id: Agent ID to wait for messages
            message_type: Optional message type filter
            timeout: Timeout in seconds

        Returns:
            Message or None if timeout
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            messages = await self.receive_messages(agent_id, clear=False)
            if message_type:
                messages = [
                    m for m in messages if m.message_type == message_type
                ]
            if messages:
                # Remove the message we're returning
                async with self._message_lock:
                    if agent_id in self._message_queue:
                        if message_type:
                            self._message_queue[agent_id] = [
                                m
                                for m in self._message_queue[agent_id]
                                if m.message_type != message_type
                            ]
                        else:
                            self._message_queue[agent_id].pop(0)
                return messages[0]

            await asyncio.sleep(0.1)  # Small delay to avoid busy waiting

        return None


__all__ = ["AgentCommunicationProtocol", "AgentMessage"]
