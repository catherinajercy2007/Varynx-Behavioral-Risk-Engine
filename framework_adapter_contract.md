# Varynx — Framework Adapter Contract

**Document:** T11.4 Framework Adapter Contract  
**Satisfies:** REQ-023  
**Phase:** Phase 1 (SimulatedEventAdapter only). Real framework adapters are Phase 2+.

---

## 1. Purpose

The Framework Adapter Contract defines the typed interface that translates framework-specific agent events into `AgentActionEvent` records for ingestion into Varynx. The Varynx core engine never imports or calls any AI agent framework; all framework coupling lives in separately packaged adapters.

---

## 2. Stability Guarantee

The `AgentActionEvent` model (defined in `varynx.models.event`) is the **stable ingestion boundary**. Its fields, types, and validation constraints are stable across minor versions. Adapters MUST produce valid `AgentActionEvent` instances that pass Pydantic v2 strict-mode validation.

---

## 3. AgentAdapterProtocol

```python
from typing import Protocol
from varynx.models.event import AgentActionEvent

class AgentAdapterProtocol(Protocol):
    """
    Typed interface for all framework adapters.
    Adapters translate framework-specific events into AgentActionEvent.
    Satisfies: REQ-023
    """

    framework_id: str
    """Unique identifier for this adapter's framework (e.g., 'langchain', 'autogen')."""

    def translate(self, framework_event: object) -> AgentActionEvent:
        """
        Translate a framework-specific event to an AgentActionEvent.

        Raises:
            AdapterTranslationError: If translation fails. Never propagated to core.
        Returns:
            AgentActionEvent: Valid instance passing strict Pydantic validation.
        """
        ...
```

---

## 4. Adapter Requirements

| Requirement | Detail |
|------------|--------|
| REQ-023.3 | Output must pass `AgentActionEvent` Pydantic v2 strict validation |
| REQ-023.5 | Exceptions must be caught, logged as `ADAPTER_TRANSLATION_ERROR`, and not propagated to pipeline |
| REQ-023.7 | Adapter must be a separately packaged optional module; core engine never imports it |
| REQ-023.8 | Invalid adapter output is rejected with `ADAPTER_OUTPUT_INVALID`; not stored |

---

## 5. SimulatedEventAdapter (Phase 1 Reference Implementation)

The `SimulatedEventAdapter` translates YAML scenario event dicts into `AgentActionEvent`. It is the only bundled adapter in Phase 1.

```python
# varynx/evaluation/runner.py — ScenarioRunner uses this pattern
event = AgentActionEvent.model_validate({
    "agent_id": se.agent_id,
    "session_id": str(session_id),
    "timestamp": ts.isoformat(),
    "action_type": se.action_type,
    "capability_requested": se.capability_requested,
    "target_resource": se.target_resource,
    "authorization_result": se.authorization_result,
    "is_simulated": True,   # REQUIRED: simulated events always set is_simulated=True
    "task_id": se.task_id,
}, strict=False)
```

The `is_simulated=True` flag is mandatory for all adapter-produced events (REQ-027.12). Simulated and live events must never be mixed in evaluation metrics.

---

## 6. Error Handling

```python
class AdapterTranslationError(Exception):
    """Raised by adapter implementations on translation failure."""
    def __init__(self, framework_id: str, description: str) -> None:
        super().__init__(f"ADAPTER_TRANSLATION_ERROR [{framework_id}]: {description}")
        self.framework_id = framework_id
```

The pipeline catches `AdapterTranslationError` and logs `ADAPTER_TRANSLATION_ERROR` with `framework_id` and sanitized description. It does not propagate to the core behavioral analysis pipeline (REQ-023.5).

---

## 7. Validation Gate

Before an adapter output enters the pipeline ingestion layer, it must pass:

```python
from pydantic import ValidationError
from varynx.models.event import AgentActionEvent

def validate_adapter_output(raw: object, framework_id: str) -> AgentActionEvent:
    try:
        return AgentActionEvent.model_validate(raw, strict=False)
    except ValidationError as exc:
        raise AdapterTranslationError(
            framework_id=framework_id,
            description=f"ADAPTER_OUTPUT_INVALID: {exc}"
        )
```

---

## 8. Phase 2 Adapters (Planned, Not Implemented)

| Adapter | Framework | Status |
|---------|-----------|--------|
| `LangChainAdapter` | LangChain | Phase 2+ |
| `AutoGenAdapter` | Microsoft AutoGen | Phase 2+ |
| `CrewAIAdapter` | CrewAI | Phase 2+ |

These are documented for design reference only. They are not bundled with Phase 1 and have no implementation in the current codebase.