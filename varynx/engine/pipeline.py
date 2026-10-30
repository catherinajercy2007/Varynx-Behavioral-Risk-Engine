"""Top-Level Pipeline Processor.

Orchestrates the full behavioral analysis pipeline:
1. Ingestion & Validation
2. Identity & Session Registry
3. Capability Lease evaluation
4. Behavioral Evidence Engine
5. Dynamic Trust Module
6. BCSE (Phase 1 stub)
7. Predictive Intelligence (Phase 1 stub)
8. Adaptive Response Engine
9. Runtime Enforcement Layer
10. Audit Log recording

Satisfies: REQ-001 through REQ-022, design.md Section 6
"""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from varynx.config import VarynxConfig
from varynx.engine.audit import AuditStore, CorrelationTracer
from varynx.engine.bcse import BCSeEngine
from varynx.engine.enforcement import EnforcementLayer
from varynx.engine.evidence import EvidenceEngine
from varynx.engine.ingestion import IngestionLayer
from varynx.engine.lease_manager import LeaseManager
from varynx.engine.prediction import PredictiveEngine
from varynx.engine.registry import IdentitySessionRegistry
from varynx.engine.response import AdaptiveResponseEngine
from varynx.engine.trust import TrustScorer
from varynx.models.audit import AuditRecordType
from varynx.models.bcse import BCSeContext
from varynx.models.enforcement import EnforcementRecord
from varynx.models.event import AgentActionEvent
from varynx.models.response import ResponseRecommendation

# Optional AWS integration -- imported conditionally to avoid hard dependency
try:
    from varynx.aws.cloudwatch_adapter import CloudWatchAdapter as _CloudWatchAdapter
except ImportError:
    _CloudWatchAdapter = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class PipelineResult:
    """Result of processing a single AgentActionEvent through the full pipeline."""

    def __init__(self) -> None:
        self.event_id: UUID | None = None
        self.correlation_id: UUID | None = None
        self.trust_score: float | None = None
        self.trust_level: str | None = None
        self.recommendation: ResponseRecommendation | None = None
        self.enforcement_record: EnforcementRecord | None = None
        self.anomalies_detected: list[str] = []
        self.error: str | None = None


class VarynxPipeline:
    """Full behavioral analysis pipeline orchestrator.

    Satisfies: design.md Section 6 (End-to-End Data Flow)
    """

    def __init__(self, config: VarynxConfig | None = None,
                 cloudwatch_adapter=None) -> None:
        self.config = config or VarynxConfig(database_url="memory://")
        # Optional CloudWatch integration. Never required for core operation.
        # If caller passes an adapter explicitly, use it.
        # Otherwise, auto-create from config when cloudwatch_enabled=True.
        if cloudwatch_adapter is not None:
            self._cloudwatch = cloudwatch_adapter
        elif self.config.aws.cloudwatch_enabled:
            try:
                from varynx.aws.cloudwatch_adapter import CloudWatchAdapter as _CW
                self._cloudwatch = _CW.from_aws_config(self.config.aws)
            except Exception:
                self._cloudwatch = None
        else:
            self._cloudwatch = None

        self.ingestion = IngestionLayer(
            past_tolerance_seconds=self.config.timestamp_past_tolerance_seconds,
            future_tolerance_seconds=self.config.timestamp_future_tolerance_seconds,
        )
        self.registry = IdentitySessionRegistry()
        self.lease_manager = LeaseManager()
        self.evidence_engine = EvidenceEngine(config=self.config.evidence)
        self.trust_scorer = TrustScorer(config=self.config.trust)
        self.bcse_engine = BCSeEngine(config=self.config.bcse)
        self.predictive_engine = PredictiveEngine(
            warning_threshold=self.config.policy.escalation_threshold
        )
        self.response_engine = AdaptiveResponseEngine(
            policy_path=self.config.policy.policy_file
            if Path(self.config.policy.policy_file).exists()
            else None
        )
        self.enforcement_layer = EnforcementLayer(
            dry_run=self.config.dry_run_mode,
            lease_manager=self.lease_manager,
        )
        self.audit_store = AuditStore()
        self.tracer = CorrelationTracer(self.audit_store)

    def process_event(
        self,
        event: AgentActionEvent,
        action_id: str | None = None,
        skip_timestamp_check: bool = False,
    ) -> PipelineResult:
        """Process a single AgentActionEvent through the full pipeline.

        Follows design.md Section 6 step-by-step.
        """
        result = PipelineResult()

        try:
            # Step 2: Ingestion & Validation
            validated = self.ingestion.validate(
                event,
                skip_timestamp_check=skip_timestamp_check,
                action_id=action_id,
            )
            result.event_id = validated.event_id
            result.correlation_id = validated.correlation_id

            # Step 3: Identity & Session Registry
            session_ctx = self.registry.process_event(validated)

            # Step 4: Capability Lease evaluation
            lease_eval = self.lease_manager.evaluate(
                agent_id=validated.agent_id,
                capability=validated.capability_requested,
                target_resource=validated.target_resource,
            )

            # Step 5: Behavioral Evidence Engine
            evidence_bundle = self.evidence_engine.process(
                validated, session_ctx, lease_eval
            )
            result.anomalies_detected = [
                r.anomaly_class.value for r in evidence_bundle.records
                if r.derivation_status == "COMPLETE"
            ]

            # Audit: evidence produced
            self.audit_store.append(
                record_type=AuditRecordType.EVIDENCE_PRODUCED,
                source_entity_id=str(evidence_bundle.bundle_id),
                payload={"bundle_id": str(evidence_bundle.bundle_id),
                         "anomaly_count": len(result.anomalies_detected)},
                correlation_id=validated.correlation_id,
                session_id=validated.session_id,
                agent_id=validated.agent_id,
            )

            # Step 6: Trust Update
            session_record = session_ctx.session_record
            started_at = session_record.started_at
            last_at = validated.timestamp
            age = (last_at - started_at).total_seconds()
            trust_state = self.trust_scorer.update(
                agent_id=validated.agent_id,
                session_id=validated.session_id,
                evidence_bundle=evidence_bundle,
                session_age_seconds=max(0.0, age),
            )
            result.trust_score = trust_state.current_score
            result.trust_level = trust_state.level.value

            # Audit: trust updated
            self.audit_store.append(
                record_type=AuditRecordType.TRUST_UPDATED,
                source_entity_id=validated.agent_id,
                payload={"new_score": trust_state.current_score,
                         "level": trust_state.level.value},
                correlation_id=validated.correlation_id,
                session_id=validated.session_id,
                agent_id=validated.agent_id,
            )

            # Step 7: BCSE evaluation (Phase 1 stub)
            bcse_ctx = BCSeContext.model_validate(
                dict(
                    context_id=str(validated.event_id),
                    proposed_action=event.model_dump(),
                    evidence_bundle=evidence_bundle.model_dump(),
                    trust_state=trust_state.model_dump(),
                    active_policy_id=self.response_engine._policy_id,
                    alternative_policies=[],
                ),
                strict=False,
            )
            bcse_result = self.bcse_engine.analyze(bcse_ctx)

            # Step 8: Trajectory projection (Phase 1 stub)
            trajectory = self.predictive_engine.project(trust_state)

            # Step 9: Response recommendation
            recommendation = self.response_engine.recommend(
                agent_id=validated.agent_id,
                correlation_id=validated.correlation_id,
                evidence_bundle=evidence_bundle,
                trust_state=trust_state,
                bcse_result=bcse_result,
                trajectory=trajectory,
                target_capability=validated.capability_requested,
                target_resource=validated.target_resource,
            )
            result.recommendation = recommendation

            # Audit: response recommended (store BEFORE enforcement, REQ-009.5)
            self.audit_store.append(
                record_type=AuditRecordType.RESPONSE_RECOMMENDED,
                source_entity_id=str(recommendation.recommendation_id),
                payload={"response_type": recommendation.response_type.value,
                         "reason_codes": [rc.code for rc in recommendation.reason_codes]},
                correlation_id=validated.correlation_id,
                session_id=validated.session_id,
                agent_id=validated.agent_id,
            )

            # Step 10: Enforcement
            enforcement_record = self.enforcement_layer.enforce(recommendation)
            result.enforcement_record = enforcement_record

            # Audit: enforcement applied
            # For ESCALATE, enrich the payload with escalation context so auditors
            # can see the pending-review state without querying the register separately.
            enforcement_payload: dict = {
                "outcome": enforcement_record.outcome.value,
                "action": enforcement_record.action_taken,
                "dry_run": enforcement_record.dry_run,
            }
            from varynx.models.response import ResponseType as _RT
            if recommendation.response_type == _RT.ESCALATE:
                escalation_entry = self.enforcement_layer.get_pending_escalation(
                    recommendation.recommendation_id
                )
                if escalation_entry:
                    enforcement_payload["escalation_status"] = escalation_entry["status"]
                    enforcement_payload["escalation_target_capability"] = escalation_entry["target_capability"]
                    enforcement_payload["escalation_reason_codes"] = escalation_entry["reason_codes"]
                    enforcement_payload["escalated_at"] = escalation_entry["escalated_at"]
                else:
                    # enforce() returned before recording (e.g. dry-run does not call _apply_action)
                    enforcement_payload["escalation_status"] = "NOT_RECORDED"
            self.audit_store.append(
                record_type=AuditRecordType.ENFORCEMENT_APPLIED,
                source_entity_id=str(enforcement_record.enforcement_id),
                payload=enforcement_payload,
                correlation_id=validated.correlation_id,
                session_id=validated.session_id,
                agent_id=validated.agent_id,
            )

            # Audit: event ingested (logged last for completeness)
            self.audit_store.append(
                record_type=AuditRecordType.EVENT_INGESTED,
                source_entity_id=str(validated.event_id),
                payload={"event_id": str(validated.event_id),
                         "action_type": validated.action_type.value},
                correlation_id=validated.correlation_id,
                session_id=validated.session_id,
                agent_id=validated.agent_id,
            )
            # Optional: publish security metrics to CloudWatch.
            # Failures are caught inside publish_pipeline_result; the pipeline
            # continues and local audit is unaffected (REQ-027 failure isolation).
            if self._cloudwatch is not None:
                try:
                    self._cloudwatch.publish_pipeline_result(result)
                except Exception as _cw_exc:
                    logger.warning("CloudWatch publish skipped: %s", _cw_exc)

        except Exception as exc:
            logger.error("Pipeline error for agent %s: %s", event.agent_id, exc, exc_info=True)
            result.error = str(exc)

        return result
