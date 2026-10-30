import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\engine\response.py')
src = p.read_text(encoding='utf-8')

# Fix: PERMIT -> WARN for invalid-policy fallback (REQ-011.7)
# Also fix the stale "MONITOR" log message (it says MONITOR, behavior was PERMIT -- misleading)
old = """        if self._policy_invalid or not self._policy:
            logger.error("POLICY_TABLE_INVALID: Falling back to MONITOR")
            return self._make_recommendation(
                agent_id=agent_id,
                correlation_id=correlation_id,
                response_type=ResponseType.PERMIT,
                evidence_bundle=evidence_bundle,
                trust_state=trust_state,
                bcse_result=bcse_result,
                trajectory=trajectory,
                reason_code_strs=["POLICY_TABLE_INVALID"],
                target_capability=target_capability,
                target_resource=target_resource,
            )"""

new = """        if self._policy_invalid or not self._policy:
            # REQ-011.7: fall back to WARN (the "MONITOR" response) when the
            # policy table is invalid or missing.  WARN permits the operation to
            # proceed but signals that the policy layer is degraded; every
            # subsequent event is still analysed by the full behavioral pipeline.
            # Using PERMIT here was a defect -- it silently allows everything
            # through with no indication that policy evaluation failed.
            logger.error("POLICY_TABLE_INVALID: Falling back to WARN (MONITOR) per REQ-011.7")
            return self._make_recommendation(
                agent_id=agent_id,
                correlation_id=correlation_id,
                response_type=ResponseType.WARN,
                evidence_bundle=evidence_bundle,
                trust_state=trust_state,
                bcse_result=bcse_result,
                trajectory=trajectory,
                reason_code_strs=["POLICY_TABLE_INVALID"],
                target_capability=target_capability,
                target_resource=target_resource,
            )"""

if old in src:
    src = src.replace(old, new, 1)
    p.write_text(src, encoding='utf-8')
    print('response.py: fallback changed PERMIT -> WARN per REQ-011.7')
else:
    print('Pattern not found')
    idx = src.find('POLICY_TABLE_INVALID')
    print(repr(src[max(0,idx-50):idx+300]))