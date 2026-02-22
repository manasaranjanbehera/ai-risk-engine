"""Workflow trigger interface. Application layer depends on this protocol."""

from typing import Protocol


class WorkflowTrigger(Protocol):
    """Protocol for starting a workflow run for a given event. Implementations may be async."""

    async def start(self, event_id: str, tenant_id: str) -> None:
        """Start workflow for the given event and tenant. No return value."""
        ...
