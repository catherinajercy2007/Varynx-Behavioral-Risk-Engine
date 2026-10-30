import os, json
os.environ.setdefault("VARYNX_DATABASE_URL", "memory://debug")

from varynx.models.bcse import BCSeContext, PolicyAlternative
from varynx.models.event import ActionType, AgentActionEvent, AuthorizationResult
from varynx.models.evidence import EvidenceBundle
from varynx.models.trust import TrustLevel, TrustState
from datetime import UTC, datetime
from uuid import uuid4

# Exact data from the dashboard request body
alt_raw = [
    {"policy_id": "permissive", "label": "Permissive (high thresholds)", "overrides": {"restrict_threshold": 0.8, "suspend_threshold": 0.9}},
    {"policy_id": "strict",     "label": "Strict (low thresholds)",     "overrides": {"restrict_threshold": 0.1, "suspend_threshold": 0.3}},
]

# Step 1: what does the route do with each dict?
alts = [PolicyAlternative.model_validate(a, strict=False) for a in alt_raw]
print("Alternatives parsed:", len(alts))
for a in alts:
    print(" ", a.policy_id, a.label, a.overrides)

# Step 2: build BCSeContext exactly as the route does
now = datetime.now(UTC)
session_id = "00000000-0000-0000-0000-000000000001"

proposed = AgentActionEvent.model_validate({
    "agent_id": "agent-bcse-demo",
    "session_id": session_id,
    "timestamp": str(now),
    "action_type": "READ",
    "capability_requested": "read:files",
    "target_resource": "/data/sensitive.csv",
    "authorization_result": AuthorizationResult.PENDING.value,
    "is_simulated": True,
}, strict=False)

trust_state = TrustState.model_validate({
    "session_id": session_id,
    "agent_id": "agent-bcse-demo",
    "current_score": 0.7,
    "level": TrustLevel.ELEVATED.value,
    "last_updated": str(now),
}, strict=False)

empty_bundle = EvidenceBundle.model_validate({
    "bundle_id": str(uuid4()),
    "session_id": session_id,
    "agent_id": "agent-bcse-demo",
    "correlation_id": str(uuid4()),
    "composite_score": 0.0,
    "correlation_window_seconds": 300.0,
    "timestamp": str(now),
    "is_simulated": True,
}, strict=False)

# THE ROUTE DOES THIS:
ctx_dict = {
    "context_id": str(uuid4()),
    "proposed_action": proposed.model_dump(),
    "evidence_bundle": empty_bundle.model_dump(),
    "trust_state": trust_state.model_dump(),
    "active_policy_id": "default_policy",
    "alternative_policies": [
        PolicyAlternative.model_validate(a, strict=False).model_dump()
        for a in alt_raw
    ],
}

print("ctx_dict alternative_policies count:", len(ctx_dict["alternative_policies"]))
print("First alt in dict:", ctx_dict["alternative_policies"][0])

ctx = BCSeContext.model_validate(ctx_dict, strict=False)
print("\\nContext after model_validate:")
print("  alternative_policies count:", len(ctx.alternative_policies))
for a in ctx.alternative_policies:
    print("  ", a.policy_id, a.overrides)

# Step 3: run the engine
from varynx.engine.bcse import BCSeEngine
engine = BCSeEngine()
result = engine.analyze(ctx)
print("\\nResult:")
print("  is_stub:", result.is_stub)
print("  divergence_score:", result.divergence_score)
print("  counterfactuals:", len(result.counterfactual_consequences))