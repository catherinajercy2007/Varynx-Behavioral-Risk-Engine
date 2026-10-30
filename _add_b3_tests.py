import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\tests\integration\test_aws_integration.py')
src = p.read_text(encoding='utf-8')

addition = '''

# ---------------------------------------------------------------------------
# B3: CloudTrail instance-scope deduplication test
# ---------------------------------------------------------------------------

class TestCloudTrailInstanceScope:
    """Verify that duplicate detection is per-instance (not process-global).

    This tests the documented limitation: a second CloudTrailAdapter instance
    will re-ingest the same event that a first instance already processed.
    """

    def test_two_instances_each_accept_same_event(self):
        """Same eventID is accepted by both instances independently."""
        event = {
            "eventID": "dedup-test-001",
            "eventName": "PutObject",
            "eventSource": "s3.amazonaws.com",
            "eventTime": "2024-06-15T14:00:00Z",
        }
        a1 = CloudTrailAdapter()
        a2 = CloudTrailAdapter()
        r1 = a1.normalize_event(event)
        r2 = a2.normalize_event(event)
        # Both instances process the event independently
        assert r1 is not None, "First instance should accept the event"
        assert r2 is not None, "Second instance (fresh) should also accept the same event"

    def test_same_instance_rejects_duplicate(self):
        """The same instance rejects a second submission of the same eventID."""
        event = {
            "eventID": "dedup-test-002",
            "eventName": "DescribeInstances",
            "eventSource": "ec2.amazonaws.com",
            "eventTime": "2024-06-15T14:00:00Z",
        }
        a = CloudTrailAdapter()
        r1 = a.normalize_event(event)
        r2 = a.normalize_event(event)
        assert r1 is not None
        assert r2 is None  # duplicate within the same instance

    def test_ingested_count_resets_on_new_instance(self):
        """health_check.ingested_count is per-instance."""
        event = {
            "eventID": "count-test-001",
            "eventName": "GetObject",
            "eventSource": "s3.amazonaws.com",
            "eventTime": "2024-06-15T14:00:00Z",
        }
        a1 = CloudTrailAdapter()
        a1.normalize_event(event)
        assert a1.health_check()["ingested_count"] == 1

        a2 = CloudTrailAdapter()
        assert a2.health_check()["ingested_count"] == 0  # fresh instance
'''

new_src = src + addition
p.write_text(new_src, encoding='utf-8')
print(f'B3 tests added: {p.stat().st_size} bytes')