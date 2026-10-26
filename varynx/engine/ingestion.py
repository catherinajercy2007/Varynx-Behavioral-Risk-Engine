"""Ingestion and Validation Layer.

Validates AgentActionEvent payloads: schema completeness, field constraints,
timestamp bounds, idempotency, correlation_id assignment, is_simulated labeling.

Satisfies: REQ-001, REQ-023
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from varynx.models.event import AgentActionEvent, ValidatedEvent


class IngestionError(Exception):
    """Raised when an event fails ingestion validation."""

    def __init__(self, reason_code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


class DuplicateActionError(IngestionError):
    """Raised when action_id duplicates an existing stored event."""

    def __init__(self, action_id: str, agent_id: str) -> None:
        super().__init__(
            reason_code="DUPLICATE_ACTION_ID",
            message=f"action_id '{action_id}' already exists for agent '{agent_id}'",
            status_code=409,
        )


class IngestionLayer:
    """Validates and stores AgentActionEvent records.

    Satisfies: REQ-001.1 through REQ-001.7
    """

    def __init__(
        self,
        past_tolerance_seconds: int = 300,
        future_tolerance_seconds: int = 60,
    ) -> None:
        self.past_tolerance_seconds = past_tolerance_seconds
        self.future_tolerance_seconds = future_tolerance_seconds
        # In-memory idempotency store (production uses DB: events.agent_action_uniq index)
        self._seen: set[tuple[str, str]] = set()

    def _check_timestamp(self, timestamp: datetime) -> None:
        """Validate event timestamp is within configured bounds (REQ-001.3)."""
        now = datetime.now(UTC)
        delta = (now - timestamp).total_seconds()
        if delta > self.past_tolerance_seconds:
            raise IngestionError(
                reason_code="TIMESTAMP_OUT_OF_RANGE",
                message=(
                    f"Event timestamp is {delta:.0f}s in the past "
                    f"(max allowed: {self.past_tolerance_seconds}s)"
                ),
            )
        if delta < -self.future_tolerance_seconds:
            raise IngestionError(
                reason_code="TIMESTAMP_OUT_OF_RANGE",
                message=(
                    f"Event timestamp is {-delta:.0f}s in the future "
                    f"(max allowed: {self.future_tolerance_seconds}s)"
                ),
            )

    def _check_idempotency(self, agent_id: str, action_id: str) -> None:
        """Enforce action_id uniqueness per agent (REQ-001.4)."""
        key = (agent_id, action_id)
        if key in self._seen:
            raise DuplicateActionError(action_id=action_id, agent_id=agent_id)
        self._seen.add(key)

    def _generate_correlation_id(self) -> UUID:
        """Generate a non-sequential, non-guessable correlation_id (REQ-001.5)."""
        # UUID4 provides 128-bit entropy as required by REQ-001.5
        return uuid4()

    def validate(
        self,
        event: AgentActionEvent,
        skip_timestamp_check: bool = False,
        action_id: str | None = None,
    ) -> ValidatedEvent:
        """Validate an AgentActionEvent and produce a ValidatedEvent.

        Args:
            event: The incoming AgentActionEvent.
            skip_timestamp_check: For testing/simulation; bypasses timestamp bounds.
            action_id: Optional external action_id for idempotency (uses session_id if None).

        Returns:
            ValidatedEvent with assigned event_id and correlation_id.

        Raises:
            IngestionError: On timestamp violation or other validation failure.
            DuplicateActionError: On action_id duplicate (HTTP 409).
        """
        if not skip_timestamp_check:
            self._check_timestamp(event.timestamp)

        # Use session_id as action_id for idempotency if not provided separately
        dedup_key = action_id or str(event.session_id)
        self._check_idempotency(event.agent_id, dedup_key)

        event_id = uuid4()
        correlation_id = self._generate_correlation_id()

        return ValidatedEvent.from_event(event, event_id, correlation_id)
