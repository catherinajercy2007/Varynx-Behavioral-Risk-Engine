# Varynx simulated resource gateway integration

## Entry point

After processing an agent event, pass its generated recommendation and a
matching `ResourceOperationRequest` to:

```python
operation_result = pipeline.execute_resource_operation(
    request,
    analysis_result.recommendation,
)
```

Initialize the pipeline with an explicitly seeded in-memory catalogue:

```python
pipeline = VarynxPipeline(
    simulated_resources={"/data/sample.txt": "initial content"}
)
```

## Fail-closed rules

- The recommendation must match agent ID, correlation ID, capability, and resource.
- `READ` requires a `read:` capability; `WRITE` requires `write:`;
  `DELETE` requires `delete:`.
- Only `PERMIT` and `WARN` are execution-permitting recommendations.
- The gateway independently checks the active lease and resource scope.
- A mismatch or non-permitting recommendation is held; a failed lease is denied.
- Behavioral decision and gateway events are appended to the existing audit hash chain.

## Scope

This integration operates only on the gateway's in-memory simulated resource
catalogue. It does not perform filesystem, S3, or AWS operations. It does not
change `process_event()` semantics: event processing remains analysis and
recommendation; resource execution is an explicit separate call.
