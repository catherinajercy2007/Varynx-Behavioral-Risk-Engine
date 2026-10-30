import pathlib

p = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx\varynx\api\routes\bcse.py")
src = p.read_text(encoding="utf-8")

old_imports = """from varynx.api.schemas import error_response, success_response
from varynx.models.bcse import BCSeContext
from varynx.models.event import ActionType, AgentActionEvent, AuthorizationResult"""

new_imports = """from varynx.api.schemas import error_response, success_response
from varynx.models.bcse import BCSeContext, PolicyAlternative
from varynx.models.event import ActionType, AgentActionEvent, AuthorizationResult"""

old_model = """class BCSeEvaluateRequest(BaseModel):
    agent_id: str
    proposed_action_type: ActionType
    proposed_resource_scope: str
    session_id: UUID
    capability_requested: str = "evaluate" """

new_model = """class PolicyAlternativeInput(BaseModel):
    policy_id: str
    label: str
    overrides: dict = {}

class BCSeEvaluateRequest(BaseModel):
    agent_id: str
    proposed_action_type: ActionType
    proposed_resource_scope: str
    session_id: UUID
    capability_requested: str = "evaluate"
    # Optional: when supplied, the Phase 2 engine runs full counterfactual analysis
    # and returns is_stub=False with populated counterfactual_consequences.
    # When omitted (default), the engine returns the Phase 1 stub (is_stub=True).
    alternative_policies: list[PolicyAlternativeInput] = []"""

old_ctx = """    context = BCSeContext.model_validate({
        "context_id": str(uuid4()),
        "proposed_action": proposed_event.model_dump(),
        "evidence_bundle": empty_bundle.model_dump(),
        "trust_state": trust_state.model_dump(),
        "active_policy_id": pipeline.response_engine._policy_id,
    }, strict=False)"""

new_ctx = """    # Convert input alternatives to the model type expected by BCSeContext
    alts = [
        PolicyAlternative.model_validate(
            {"policy_id": a.policy_id, "label": a.label, "overrides": a.overrides},
            strict=False,
        )
        for a in body.alternative_policies
    ]

    context = BCSeContext.model_validate({
        "context_id": str(uuid4()),
        "proposed_action": proposed_event.model_dump(),
        "evidence_bundle": empty_bundle.model_dump(),
        "trust_state": trust_state.model_dump(),
        "active_policy_id": pipeline.response_engine._policy_id,
        "alternative_policies": [a.model_dump() for a in alts],
    }, strict=False)"""

if old_imports in src and old_model in src and old_ctx in src:
    src = src.replace(old_imports, new_imports, 1)
    src = src.replace(old_model, new_model, 1)
    src = src.replace(old_ctx, new_ctx, 1)
    p.write_text(src, encoding="utf-8")
    print(f"bcse.py updated: {p.stat().st_size} bytes")
else:
    miss = []
    if old_imports not in src: miss.append("imports")
    if old_model not in src: miss.append("model")
    if old_ctx not in src: miss.append("context")
    print("PATTERNS NOT FOUND:", miss)
    print(repr(src[:400]))
