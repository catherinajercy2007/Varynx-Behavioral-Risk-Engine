# Varynx Persistent Security Patch

## Contents

- `varynx/engine/audit.py`
  - Adds `SQLiteAuditStore`, preserving the existing `AuditStore` interface.
  - Uses SQLite WAL (for file-backed DBs), `synchronous=FULL`, busy timeout,
    and `BEGIN IMMEDIATE` for serialized appends.
  - Persists record JSON and hash metadata.
  - Maintains a database-local checkpoint containing record count and chain head.
  - Detects record edits, metadata mismatch, truncation, and missing checkpoint.
  - Refuses new appends when existing integrity checks fail.
- `varynx/engine/resource_gateway.py`
  - Adds `SQLiteIdempotencyStore`.
  - Persists request fingerprints and IN_PROGRESS / COMPLETED / INDETERMINATE state.
  - Replays completed results; rejects changed payloads; does not auto-retry
    in-progress or indeterminate requests.
  - Keeps existing in-memory behavior as the default.
- `varynx/engine/pipeline.py`
  - Adds optional `persistence_path` to `VarynxPipeline`.
  - When supplied, stores audit and idempotency databases under that directory.
  - Adds `close()` for graceful shutdown.
- `tests/unit/test_persistent_security.py`
  - Restart, tamper, truncation, concurrent-claim, and replay tests.

## Apply on Windows

From the repository root, first preserve a copy of the current changed files:

```powershell
Copy-Item .\varynx\engine\audit.py .\varynx\engine\audit.py.pre-persistence
Copy-Item .\varynx\engine\resource_gateway.py .\varynx\engine\resource_gateway.py.pre-persistence
Copy-Item .\varynx\engine\pipeline.py .\varynx\engine\pipeline.py.pre-persistence
```

Extract the patch ZIP into the repository root, preserving the folder structure.

## Opt-in usage

```python
from varynx.engine.pipeline import VarynxPipeline

pipeline = VarynxPipeline(
    persistence_path="var/varynx-state",
    simulated_resources={"/data/item.txt": "initial"},
)

try:
    # Process events and execute authorized simulated resource operations.
    ...
finally:
    pipeline.close()
```

This creates:
- `var/varynx-state/audit.sqlite3`
- `var/varynx-state/idempotency.sqlite3`

Without `persistence_path`, the existing in-memory behavior remains unchanged.

## Interrupted-request recovery

A request left IN_PROGRESS after a process crash is not automatically executed again.
During a controlled startup, after confirming all old workers are stopped:

```python
recovered = pipeline.idempotency_store.recover_incomplete()
```

Those requests become INDETERMINATE. Reconcile their actual outcome before issuing
a new request with a new request ID. Do not run recovery while any prior worker may
still be executing.

## Important limitations

1. This patch persists the audit log and idempotency ledger only. Agent/session
   registry state, capability leases, trust state, and the simulated resource
   catalogue are not persisted.
2. The simulated resource gateway still operates on in-memory resources. On restart,
   seed the catalogue from the authoritative resource state. The durable ledger
   prevents automatic replay of a completed request, but it does not make the
   simulated catalogue durable.
3. SQLite cannot atomically commit a database ledger update together with an
   arbitrary external side effect (for example, an S3 DELETE). If a process stops
   after the external operation but before COMPLETED is committed, the request
   remains IN_PROGRESS and must be treated as INDETERMINATE. This is deliberately
   at-most-once/fail-closed behavior, not exactly-once execution.
4. The audit checkpoint is stored in the same SQLite database. It detects accidental
   or partial edits/truncation, but a privileged attacker able to rewrite the entire
   database can rewrite both records and checkpoint. Production tamper resistance
   requires an independently protected checkpoint or remote append-only/WORM sink.
5. This implementation is suitable for a single-host SQLite deployment. For multiple
   hosts, use a shared transactional database and a resource adapter with durable
   operation semantics.

## Verification in the patch-building environment

- Unit + integration + benchmark tests: 408 passed.
- Python compileall: passed.
- Full test collection could not run here because `hypothesis` is not installed;
  four property-test modules fail collection for that environmental dependency.
- Ruff is not installed in this environment. Run targeted Ruff in the project's
  `.venv` after applying the patch.
