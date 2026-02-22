"""Dummy workflow trigger implementation: logs only. Used when no real workflow is wired."""

import logging

logger = logging.getLogger(__name__)


class DummyWorkflowTrigger:
    """Placeholder WorkflowTrigger that only logs. Does not fail the transaction."""

    async def start(self, event_id: str, tenant_id: str) -> None:
        logger.info(
            "workflow_trigger_placeholder",
            extra={
                "event_id": event_id,
                "tenant_id": tenant_id,
            },
        )
