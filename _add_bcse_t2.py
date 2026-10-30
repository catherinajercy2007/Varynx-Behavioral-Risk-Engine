import pathlib
p = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx\tests\integration\test_api_routes.py")
src = p.read_text(encoding="utf-8")

addition = """

    def test_bcse_with_alternatives_is_stub_false(self):
        client = _make_client()
        body = {
            "agent_id": "ag-bcse-phase2",
            "proposed_action_type": "READ",
            "proposed_resource_scope": "/data/test.csv",
            "session_id": str(uuid4()),
            "capability_requested": "read:files",
            "alternative_policies": [
                {"policy_id": "permissive", "label": "Permissive", "overrides": {"restrict_threshold": 0.9}},
                {"policy_id": "strict", "label": "Strict", "overrides": {"restrict_threshold": 0.05}},
            ],
        }
        r = client.post("/api/v1/bcse/evaluate", json=body)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["is_stub"] is False, "Phase 2 should run when alternatives supplied"
        assert len(d["counterfactual_consequences"]) == 2
        assert 0.0 <= d["divergence_score"] <= 1.0
        for cf in d["counterfactual_consequences"]:
            assert cf["is_projected"] is True

    def test_bcse_empty_alternatives_stays_stub(self):
        client = _make_client()
        body = {
            "agent_id": "ag-bcse-empty-alts",
            "proposed_action_type": "WRITE",
            "proposed_resource_scope": "/data/out.csv",
            "session_id": str(uuid4()),
            "alternative_policies": [],
        }
        r = client.post("/api/v1/bcse/evaluate", json=body)
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["is_stub"] is True
        assert d["counterfactual_consequences"] == []
"""

marker = "    def test_bcse_low_history_warning_when_no_prior_events(self):"
idx = src.find(marker)
if idx == -1:
    print("marker not found")
else:
    next_class = src.find("\\nclass ", idx + 1)
    insert_at = next_class if next_class != -1 else len(src)
    src = src[:insert_at] + addition + src[insert_at:]
    p.write_text(src, encoding="utf-8")
    print("test added:", p.stat().st_size, "bytes")