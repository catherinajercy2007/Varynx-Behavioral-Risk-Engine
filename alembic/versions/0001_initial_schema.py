"""Initial schema — all 9 Varynx tables.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

Satisfies: T1.2, REQ-017, design.md Section 14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Subsystem: Identity
    # ==========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id            TEXT PRIMARY KEY,
            registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            declared_capability_scope  JSONB NOT NULL DEFAULT '[]',
            authorized_resource_scope  JSONB NOT NULL DEFAULT '[]',
            owning_principal    TEXT NOT NULL,
            scope_escalation_count  INTEGER NOT NULL DEFAULT 0,
            metadata            JSONB NOT NULL DEFAULT '{}'
        )
    """)
    # CONSTRAINT: agent_id and owning_principal must not be updated after insert (REQ-002.5)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id          UUID PRIMARY KEY,
            agent_id            TEXT NOT NULL REFERENCES agents(agent_id),
            started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_event_at       TIMESTAMPTZ,
            ended_at            TIMESTAMPTZ,
            current_trust       FLOAT NOT NULL DEFAULT 0.7
                CHECK (current_trust >= 0.0 AND current_trust <= 1.0),
            trust_level         TEXT NOT NULL DEFAULT 'ELEVATED',
            state               TEXT NOT NULL DEFAULT 'ACTIVE',
            resource_spread     JSONB NOT NULL DEFAULT '{}',
            capability_spread   JSONB NOT NULL DEFAULT '{}'
        )
    """)

    # ==========================================================================
    # Subsystem: Behavioral Event Log (TimescaleDB hypertable)
    # ==========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id                UUID NOT NULL,
            agent_id                TEXT NOT NULL,
            session_id              UUID NOT NULL,
            correlation_id          UUID NOT NULL,
            timestamp               TIMESTAMPTZ NOT NULL,
            task_id                 TEXT,
            action_type             TEXT NOT NULL,
            capability_requested    TEXT NOT NULL,
            target_resource         TEXT NOT NULL,
            execution_context       JSONB NOT NULL DEFAULT '{}',
            authorization_result    TEXT NOT NULL,
            behavioral_signals      JSONB NOT NULL DEFAULT '{}',
            trust_signal            FLOAT CHECK (
                trust_signal IS NULL OR (trust_signal >= 0.0 AND trust_signal <= 1.0)
            ),
            is_simulated            BOOLEAN NOT NULL,
            raw_payload             JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (event_id, timestamp)
        )
    """)
    # TimescaleDB hypertable — only if extension is available
    try:
        op.execute("SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE)")
    except Exception:
        pass  # TimescaleDB not available in all environments; table still functions

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS events_agent_action_uniq
        ON events (agent_id, event_id)
    """)

    # ==========================================================================
    # Subsystem: Evidence Store
    # ==========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence_records (
            evidence_id             UUID PRIMARY KEY,
            event_id                UUID NOT NULL,
            session_id              UUID NOT NULL,
            agent_id                TEXT NOT NULL,
            correlation_id          UUID NOT NULL,
            anomaly_class           TEXT NOT NULL,
            score                   FLOAT NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
            weight                  FLOAT NOT NULL CHECK (weight >= 0.0 AND weight <= 1.0),
            detector_id             TEXT NOT NULL,
            contributing_signals    JSONB NOT NULL DEFAULT '[]',
            provenance              JSONB NOT NULL DEFAULT '{}',
            timestamp               TIMESTAMPTZ NOT NULL,
            is_simulated            BOOLEAN NOT NULL,
            content_hash            TEXT NOT NULL,
            derivation_status       TEXT NOT NULL DEFAULT 'COMPLETE'
        )
    """)
    # No UPDATE or DELETE permitted on this table after initial insert (REQ-003.5)

    op.execute("""
        CREATE TABLE IF NOT EXISTS trust_history (
            entry_id                UUID PRIMARY KEY,
            session_id              UUID NOT NULL,
            agent_id                TEXT NOT NULL,
            timestamp               TIMESTAMPTZ NOT NULL,
            prior_score             FLOAT NOT NULL,
            delta                   FLOAT NOT NULL,
            new_score               FLOAT NOT NULL CHECK (new_score >= 0.0 AND new_score <= 1.0),
            contributing_evidence_ids  JSONB NOT NULL DEFAULT '[]',
            excluded_incomplete_count  INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ==========================================================================
    # Subsystem: Decision Store
    # ==========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS capability_leases (
            lease_id                UUID PRIMARY KEY,
            agent_id                TEXT NOT NULL REFERENCES agents(agent_id),
            session_id              UUID NOT NULL,
            capability              TEXT NOT NULL,
            resource_scope          JSONB NOT NULL DEFAULT '{}',
            activation_timestamp    TIMESTAMPTZ NOT NULL,
            expiry_timestamp        TIMESTAMPTZ,
            issuing_principal       TEXT NOT NULL,
            issuing_policy_id       TEXT NOT NULL,
            state                   TEXT NOT NULL DEFAULT 'ACTIVE',
            state_history           JSONB NOT NULL DEFAULT '[]'
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS response_recommendations (
            recommendation_id       UUID PRIMARY KEY,
            agent_id                TEXT NOT NULL,
            correlation_id          UUID NOT NULL,
            response_type           TEXT NOT NULL,
            reason_codes            JSONB NOT NULL DEFAULT '[]',
            evidence_bundle_id      UUID NOT NULL,
            trust_snapshot          JSONB NOT NULL DEFAULT '{}',
            bcse_result_id          UUID,
            trajectory_projection_id UUID,
            rationale               TEXT NOT NULL,
            policy_id               TEXT NOT NULL,
            policy_version          TEXT NOT NULL,
            timestamp               TIMESTAMPTZ NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS enforcement_records (
            enforcement_id          UUID PRIMARY KEY,
            source_recommendation_id UUID NOT NULL,
            action_taken            TEXT NOT NULL,
            target_agent_id         TEXT NOT NULL,
            target_resource_scope   TEXT,
            action_timestamp        TIMESTAMPTZ NOT NULL,
            outcome                 TEXT NOT NULL,
            outcome_reason          TEXT,
            dry_run                 BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    # ==========================================================================
    # Subsystem: Audit Log (append-only)
    # CRITICAL: Application role MUST NOT have UPDATE or DELETE on this table (REQ-013.3)
    # ==========================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            record_id               UUID PRIMARY KEY,
            timestamp               TIMESTAMPTZ NOT NULL,
            record_type             TEXT NOT NULL,
            source_entity_id        TEXT NOT NULL,
            correlation_id          UUID,
            session_id              UUID,
            agent_id                TEXT,
            payload                 JSONB NOT NULL DEFAULT '{}',
            prior_record_hash       TEXT,
            record_hash             TEXT NOT NULL
        )
    """)


def downgrade() -> None:
    # Drop in reverse dependency order
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS enforcement_records")
    op.execute("DROP TABLE IF EXISTS response_recommendations")
    op.execute("DROP TABLE IF EXISTS capability_leases")
    op.execute("DROP TABLE IF EXISTS trust_history")
    op.execute("DROP TABLE IF EXISTS evidence_records")
    op.execute("DROP TABLE IF EXISTS events")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS agents")