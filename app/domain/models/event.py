"""Domain model for events. Pure business semantics — no ORM or infrastructure."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional

from app.domain.exceptions import InvalidStatusTransitionError


class EventStatus(str, Enum):
    """Lifecycle status for domain events. Transitions are validated."""

    RECEIVED = "received"  # Persisted at application boundary; first stored state
    CREATED = "created"
    VALIDATED = "validated"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


# Allowed status transitions: from_status -> set of valid next statuses
_STATUS_TRANSITIONS: Dict[EventStatus, FrozenSet[EventStatus]] = {
    EventStatus.RECEIVED: frozenset({EventStatus.VALIDATED, EventStatus.REJECTED}),
    EventStatus.CREATED: frozenset({EventStatus.VALIDATED, EventStatus.REJECTED}),
    EventStatus.VALIDATED: frozenset({EventStatus.PROCESSING}),
    EventStatus.PROCESSING: frozenset(
        {EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.FAILED}
    ),
    EventStatus.APPROVED: frozenset(),
    EventStatus.REJECTED: frozenset(),
    EventStatus.FAILED: frozenset(),
}


def _validate_transition(current: EventStatus, new: EventStatus) -> None:
    """Validate that transition from current to new is allowed. Raises if invalid."""
    allowed = _STATUS_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise InvalidStatusTransitionError(
            f"Invalid status transition from {current.value} to {new.value}"
        )


@dataclass(frozen=False)
class BaseEvent:
    """
    Shared properties for domain events. Subclasses add entity-specific fields.
    Status must be changed only via transition_to() to enforce lifecycle rules.
    """

    event_id: str
    tenant_id: str
    status: EventStatus
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    def transition_to(self, new_status: EventStatus) -> None:
        """
        Transition to a new status if allowed. Mutates status in place.
        Raises InvalidStatusTransitionError if transition is not allowed.
        """
        _validate_transition(self.status, new_status)
        object.__setattr__(self, "status", new_status)


@dataclass
class RiskEvent(BaseEvent):
    """Domain entity for risk-related events. Shares base event props plus risk-specific fields."""

    risk_score: Optional[float] = None
    category: Optional[str] = None


@dataclass
class ComplianceEvent(BaseEvent):
    """Domain entity for compliance-related events. Shares base event props plus compliance-specific fields."""

    regulation_ref: Optional[str] = None
    compliance_type: Optional[str] = None
