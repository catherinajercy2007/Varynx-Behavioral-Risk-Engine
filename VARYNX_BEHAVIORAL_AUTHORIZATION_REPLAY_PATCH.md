# Varynx Behavioral Authorization and Replay Protection Patch

## Changes

1. `LeaseManager.evaluate()` accepts an optional `session_id`. When supplied,
   only leases belonging to that exact agent/session pair can authorize access.
2. The event pipeline passes the validated event session ID into lease evaluation.
3. The simulated resource gateway requires a session ID and evaluates the lease
   against that session.
4. The gateway now protects its in-memory operation catalogue with an `RLock`.
5. Request IDs are idempotent within one gateway process. The request fingerprint
   includes the full request payload and the behavioral-permit decision.
6. An identical replay returns the cached result without repeating the operation.
   Reusing an ID with a changed payload or changed behavioral decision returns
   `REPLAY_CONFLICT` and does not mutate the resource.
7. Tests cover session mismatch, duplicate WRITE/DELETE, changed-payload collisions,
   and attempts to upgrade a held request by reusing its request ID.

## Important semantics

- A held request is final for that request ID. A later approved attempt must use a
  fresh request ID. This prevents an authorization decision from being upgraded
  after the request has already been evaluated.
- Replay protection is process-local and in-memory. It does not survive restart and
  does not coordinate multiple workers/hosts. Production deployment needs a durable,
  atomic idempotency store (for example, a database unique constraint/transaction).
- The gateway still operates only on an in-memory simulated resource catalogue.
- The audit store's existing hash-chain verifier already detects record tampering;
  the integration tests continue to verify chain validity after resource operations.

## Files in this patch

- `varynx/engine/resource_gateway.py`
- `varynx/engine/lease_manager.py`
- `varynx/engine/pipeline.py`
- `tests/unit/test_resource_gateway.py`
- `tests/integration/test_resource_gateway_pipeline.py`
