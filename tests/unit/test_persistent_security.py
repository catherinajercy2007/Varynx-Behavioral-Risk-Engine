"""Restart and durability tests for opt-in SQLite security stores."""
from uuid import uuid4

from varynx.engine.audit import AuditRecordType, SQLiteAuditStore
from varynx.engine.lease_manager import LeaseManager
from varynx.engine.resource_gateway import (
    ResourceOperation,
    ResourceOperationRequest,
    SimulatedResourceGateway,
    SQLiteIdempotencyStore,
)


def _lease_manager(session_id):
    manager = LeaseManager()
    manager.create_lease(
        agent_id="agent-persistent",
        session_id=session_id,
        capability="write:files",
        resource_scope={"resources": ["/data"]},
        issuing_principal="test-admin",
        issuing_policy_id="test-policy",
    )
    return manager


def _request(session_id, **overrides):
    values = {
        "agent_id": "agent-persistent",
        "capability": "write:files",
        "target_resource": "/data/item.txt",
        "operation": ResourceOperation.WRITE,
        "value": "durable-value",
        "session_id": session_id,
        "correlation_id": uuid4(),
    }
    values.update(overrides)
    return ResourceOperationRequest(**values)


def test_sqlite_audit_store_survives_close_and_reopen(tmp_path):
    db_path = tmp_path / "audit.sqlite3"
    correlation_id = uuid4()

    first = SQLiteAuditStore(str(db_path))
    record = first.append(
        AuditRecordType.EVENT_INGESTED,
        "event-1",
        {"action": "write"},
        correlation_id=correlation_id,
    )
    first.close()

    reopened = SQLiteAuditStore(str(db_path))
    records = reopened.query_by_correlation_id(correlation_id)
    assert len(records) == 1
    assert records[0].record_id == record.record_id
    assert reopened.verify_chain() == (True, [])
    reopened.close()


def test_sqlite_audit_store_serializes_appends_from_multiple_instances(tmp_path):
    db_path = tmp_path / "shared-audit.sqlite3"
    first = SQLiteAuditStore(str(db_path))
    second = SQLiteAuditStore(str(db_path))

    first.append(AuditRecordType.EVENT_INGESTED, "event-1", {})
    second.append(AuditRecordType.TRUST_UPDATED, "agent-1", {})
    first.append(AuditRecordType.RESPONSE_RECOMMENDED, "recommendation-1", {})

    valid, violations = second.verify_chain()
    assert valid, violations
    assert len(second.all_records()) == 3
    first.close()
    second.close()


def test_sqlite_audit_store_detects_database_record_tampering(tmp_path):
    import sqlite3

    db_path = tmp_path / "tampered-audit.sqlite3"
    store = SQLiteAuditStore(str(db_path))
    store.append(AuditRecordType.EVENT_INGESTED, "event-1", {"value": "original"})
    store.close()

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        "SELECT record_id, record_json FROM audit_records"
    ).fetchone()
    import json

    payload = json.loads(row[1])
    payload["payload"]["value"] = "tampered"
    connection.execute(
        "UPDATE audit_records SET record_json = ? WHERE record_id = ?",
        (json.dumps(payload), row[0]),
    )
    connection.commit()
    connection.close()

    reopened = SQLiteAuditStore(str(db_path))
    valid, violations = reopened.verify_chain()
    assert not valid
    assert any("TAMPER_DETECTED" in item for item in violations)
    reopened.close()


def test_durable_gateway_returns_completed_result_after_restart(tmp_path):
    session_id = uuid4()
    request = _request(session_id)
    audit = SQLiteAuditStore(str(tmp_path / "audit.sqlite3"))
    ledger = SQLiteIdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    gateway = SimulatedResourceGateway(
        _lease_manager(session_id),
        audit,
        {"/data/item.txt": "initial"},
        idempotency_store=ledger,
    )

    first = gateway.execute(request, behavioral_permit=True)
    assert first.executed
    assert gateway.snapshot()["/data/item.txt"] == "durable-value"
    ledger.close()
    audit.close()

    # The simulated resource catalogue is deliberately re-seeded to represent
    # the already-committed external state. The restarted gateway must not write again.
    audit2 = SQLiteAuditStore(str(tmp_path / "audit.sqlite3"))
    ledger2 = SQLiteIdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    restarted = SimulatedResourceGateway(
        _lease_manager(session_id),
        audit2,
        {"/data/item.txt": "durable-value"},
        idempotency_store=ledger2,
    )
    replay = restarted.execute(request, behavioral_permit=True)

    assert replay.model_dump() == first.model_dump()
    assert restarted.snapshot()["/data/item.txt"] == "durable-value"
    assert len(audit2.all_records()) > 0
    assert audit2.verify_chain()[0]
    ledger2.close()
    audit2.close()


def test_durable_gateway_rejects_changed_payload_after_restart(tmp_path):
    session_id = uuid4()
    request = _request(session_id)
    audit = SQLiteAuditStore(str(tmp_path / "audit.sqlite3"))
    ledger = SQLiteIdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    gateway = SimulatedResourceGateway(
        _lease_manager(session_id), audit, {"/data/item.txt": "initial"},
        idempotency_store=ledger,
    )
    assert gateway.execute(request, behavioral_permit=True).executed
    ledger.close()
    audit.close()

    audit2 = SQLiteAuditStore(str(tmp_path / "audit.sqlite3"))
    ledger2 = SQLiteIdempotencyStore(str(tmp_path / "idempotency.sqlite3"))
    restarted = SimulatedResourceGateway(
        _lease_manager(session_id), audit2, {"/data/item.txt": "durable-value"},
        idempotency_store=ledger2,
    )
    conflict = restarted.execute(
        request.model_copy(update={"value": "different"}),
        behavioral_permit=True,
    )
    assert conflict.status == "REPLAY_CONFLICT"
    assert not conflict.executed
    ledger2.close()
    audit2.close()


def test_recovered_in_progress_request_is_indeterminate_not_reexecuted(tmp_path):
    session_id = uuid4()
    request = _request(session_id)
    ledger_path = tmp_path / "idempotency.sqlite3"
    ledger = SQLiteIdempotencyStore(str(ledger_path))
    import hashlib
    import json

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "behavioral_permit": True,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    assert ledger.claim(request.request_id, fingerprint)[0] == "NEW"
    assert ledger.recover_incomplete() == 1
    ledger.close()

    reopened = SQLiteIdempotencyStore(str(ledger_path))
    audit = SQLiteAuditStore(str(tmp_path / "audit.sqlite3"))
    gateway = SimulatedResourceGateway(
        _lease_manager(session_id),
        audit,
        {"/data/item.txt": "initial"},
        idempotency_store=reopened,
    )
    result = gateway.execute(request, behavioral_permit=True)
    assert result.status == "INDETERMINATE"
    assert not result.executed
    assert gateway.snapshot()["/data/item.txt"] == "initial"
    reopened.close()
    audit.close()


def test_pipeline_can_opt_into_sqlite_persistence(tmp_path):
    from varynx.engine.pipeline import VarynxPipeline

    pipeline = VarynxPipeline(persistence_path=tmp_path / "state")
    assert isinstance(pipeline.audit_store, SQLiteAuditStore)
    assert isinstance(pipeline.idempotency_store, SQLiteIdempotencyStore)
    pipeline.audit_store.append(AuditRecordType.SESSION_CREATED, "session-1", {})
    assert pipeline.audit_store.verify_chain()[0]
    pipeline.idempotency_store.close()
    pipeline.audit_store.close()


def test_sqlite_audit_store_detects_record_deletion_from_checkpoint(tmp_path):
    import sqlite3

    db_path = tmp_path / "deleted-audit.sqlite3"
    store = SQLiteAuditStore(str(db_path))
    store.append(AuditRecordType.EVENT_INGESTED, "event-1", {})
    store.append(AuditRecordType.TRUST_UPDATED, "agent-1", {})
    store.close()

    connection = sqlite3.connect(db_path)
    connection.execute(
        "DELETE FROM audit_records WHERE sequence = (SELECT MAX(sequence) FROM audit_records)"
    )
    connection.commit()
    connection.close()

    reopened = SQLiteAuditStore(str(db_path))
    valid, violations = reopened.verify_chain()
    assert not valid
    assert any("record count differs from checkpoint" in item for item in violations)
    try:
        reopened.append(AuditRecordType.EVENT_INGESTED, "event-2", {})
    except RuntimeError as exc:
        assert "AUDIT_CHAIN_INVALID" in str(exc)
    else:
        raise AssertionError("Append must fail closed after detected truncation")
    reopened.close()


def test_sqlite_idempotency_claim_is_serialized_across_store_instances(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    db_path = tmp_path / "concurrent-idempotency.sqlite3"
    first_store = SQLiteIdempotencyStore(str(db_path))
    second_store = SQLiteIdempotencyStore(str(db_path))
    request_id = uuid4()

    def claim(store):
        return store.claim(request_id, "same-fingerprint")[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(claim, [first_store, second_store]))

    assert sorted(outcomes) == ["IN_PROGRESS", "NEW"]
    first_store.close()
    second_store.close()


def test_sqlite_audit_store_detects_missing_checkpoint(tmp_path):
    import sqlite3

    db_path = tmp_path / "missing-checkpoint.sqlite3"
    store = SQLiteAuditStore(str(db_path))
    store.append(AuditRecordType.EVENT_INGESTED, "event-1", {})
    store.close()

    connection = sqlite3.connect(db_path)
    connection.execute("DELETE FROM audit_state WHERE singleton = 1")
    connection.commit()
    connection.close()

    reopened = SQLiteAuditStore(str(db_path))
    valid, violations = reopened.verify_chain()
    assert not valid
    assert any("checkpoint is missing" in item for item in violations)
    reopened.close()
