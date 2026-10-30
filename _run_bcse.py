import os, json
os.environ.setdefault("VARYNX_DATABASE_URL", "memory://bcse-run")

from varynx.engine.pipeline import VarynxPipeline
from varynx.engine.bcse import BCSeEngine
from varynx.models.bcse import BCSeContext, PolicyAlternative
from varynx.models.evidence import EvidenceBundle
from varynx.models.trust import TrustState, TrustLevel
from datetime import UTC, datetime
from uuid import uuid4

now = datetime.now(UTC).isoformat()
session_id = str(uuid4())

# Build trust state (no prior events -> low_history_warning expected)
trust_state = TrustState.model_validate({
    "session_id": session_id,
    "agent_id": "agent-bcse-demo",
    "current_score": 0.55,
    "level": TrustLevel.GUARDED.value,
    "last_updated": now,
    "history": [],
}, strict=False)

# Build empty evidence bundle
bundle = EvidenceBundle.model_validate({
    "bundle_id": str(uuid4()),
    "session_id": session_id,
    "agent_id": "agent-bcse-demo",
    "correlation_id": str(uuid4()),
    "composite_score": 0.45,
    "correlation_window_seconds": 300.0,
    "timestamp": now,
    "is_simulated": True,
}, strict=False)

# Two alternative policies for Phase 2 evaluation
alts = [
    PolicyAlternative.model_validate({
        "policy_id": "permissive",
        "label": "Permissive (high thresholds)",
        "overrides": {"restrict_threshold": 0.9, "suspend_threshold": 0.95},
    }, strict=False),
    PolicyAlternative.model_validate({
        "policy_id": "strict",
        "label": "Strict (low thresholds)",
        "overrides": {"restrict_threshold": 0.05, "suspend_threshold": 0.20},
    }, strict=False),
]

from varynx.models.event import AgentActionEvent, ActionType, AuthorizationResult
proposed = AgentActionEvent.model_validate({
    "agent_id": "agent-bcse-demo",
    "session_id": session_id,
    "timestamp": now,
    "action_type": ActionType.WRITE.value,
    "capability_requested": "write:files",
    "target_resource": "/data/sensitive.csv",
    "authorization_result": AuthorizationResult.PENDING.value,
    "is_simulated": True,
}, strict=False)

ctx = BCSeContext.model_validate({
    "context_id": str(uuid4()),
    "proposed_action": proposed.model_dump(),
    "evidence_bundle": bundle.model_dump(),
    "trust_state": trust_state.model_dump(),
    "active_policy_id": "default",
    "alternative_policies": [a.model_dump() for a in alts],
}, strict=False)

engine = BCSeEngine()
result = engine.analyze(ctx)

print("=" * 60)
print("BCSE EVALUATION RESULT")
print("=" * 60)
print(f"bcse_id          : {result.bcse_id}")
print(f"agent_id         : {result.agent_id}")
print(f"is_stub          : {result.is_stub}")
print(f"low_history_warn : {result.low_history_warning}")
print(f"divergence_score : {result.divergence_score}")
print()
print("--- Active Policy Consequence ---")
ac = result.active_consequence
print(f"  policy_id         : {ac.policy_id}")
print(f"  projected_response: {ac.projected_response}")
print(f"  risk_level        : {ac.risk_level}")
print(f"  confidence        : {ac.confidence}")
print(f"  uncertainty_score : {ac.uncertainty_score}")
print(f"  is_projected      : {ac.is_projected}")
print(f"  rationale         : {ac.rationale[:80]}...")
print()
print(f"--- Counterfactual Consequences ({len(result.counterfactual_consequences)}) ---")
for i, cf in enumerate(result.counterfactual_consequences, 1):
    print(f"  [{i}] policy={cf.policy_id}  response={cf.projected_response}  risk={cf.risk_level}  conf={cf.confidence}")
print()
print("PHASE 2 ENGINE ACTIVE:", not result.is_stub)
print("=" * 60)