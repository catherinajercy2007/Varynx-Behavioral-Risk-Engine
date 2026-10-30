import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\tests\property\test_response_properties.py')
src = p.read_text(encoding='utf-8')

old = '''def test_policy_table_invalid_fallback():
    """Invalid policy \u2192 PERMIT fallback and POLICY_TABLE_INVALID logged (REQ-011.7)."""
    engine = AdaptiveResponseEngine(policy_path=None)
    engine._policy_invalid = True
    ts = make_trust_state(0.5, TrustLevel.GUARDED)
    rec = engine.recommend("ag-inv", uuid4(), make_bundle(0.0), ts)
    # Fallback is PERMIT (logged as POLICY_TABLE_INVALID)
    assert rec.response_type == ResponseType.PERMIT
    assert any(rc.code == "POLICY_TABLE_INVALID" for rc in rec.reason_codes)'''

new = '''def test_policy_table_invalid_fallback():
    """Invalid policy \u2192 WARN (MONITOR) fallback and POLICY_TABLE_INVALID logged (REQ-011.7).

    REQ-011.7 requires MONITOR (mapped to WARN in this codebase) as the fallback,
    not PERMIT.  PERMIT was a defect -- it silently allowed all requests when the
    policy table was missing or corrupt.  WARN preserves operation continuity while
    making the policy failure visible in the recommendation's reason codes.
    """
    engine = AdaptiveResponseEngine(policy_path=None)
    engine._policy_invalid = True
    ts = make_trust_state(0.5, TrustLevel.GUARDED)
    rec = engine.recommend("ag-inv", uuid4(), make_bundle(0.0), ts)
    # Fallback is WARN per REQ-011.7 (MONITOR, not PERMIT)
    assert rec.response_type == ResponseType.WARN, (
        f"Expected WARN fallback per REQ-011.7, got {rec.response_type}"
    )
    assert any(rc.code == "POLICY_TABLE_INVALID" for rc in rec.reason_codes)'''

if old in src:
    src = src.replace(old, new, 1)
    p.write_text(src, encoding='utf-8')
    print('test updated: PERMIT -> WARN')
else:
    print('Pattern not found -- searching for partial match')
    idx = src.find('test_policy_table_invalid_fallback')
    print(repr(src[idx:idx+400]))