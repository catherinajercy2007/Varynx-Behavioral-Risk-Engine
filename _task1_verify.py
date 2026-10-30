import os, json
os.environ.setdefault('VARYNX_DATABASE_URL', 'memory://verify')
from fastapi.testclient import TestClient
import varynx.api.app as api_app
from varynx.engine.pipeline import VarynxPipeline
from varynx.config import VarynxConfig
from varynx.api.app import create_app
from uuid import uuid4

api_app._pipeline = VarynxPipeline()
cfg = VarynxConfig(database_url='memory://', api_key=None)
app = create_app(config=cfg)
client = TestClient(app, raise_server_exceptions=True)

# Task 1a: health
r = client.get('/api/v1/health')
print('HEALTH:', r.status_code, r.json()['data']['status'])

# Task 1b: BCSE OpenAPI schema includes alternative_policies?
spec = client.get('/api/v1/openapi.json').json()
props = spec['components']['schemas']['BCSeEvaluateRequest']['properties']
print('BCSE schema fields:', list(props.keys()))
print('alternative_policies present:', 'alternative_policies' in props)

# Task 1c: BCSE with alternatives -> Phase 2
r2 = client.post('/api/v1/bcse/evaluate', json={
    'agent_id': 'verify-agent',
    'proposed_action_type': 'READ',
    'proposed_resource_scope': '/data/test.csv',
    'session_id': str(uuid4()),
    'capability_requested': 'read:files',
    'alternative_policies': [
        {'policy_id': 'permissive', 'label': 'Permissive', 'overrides': {'restrict_threshold': 0.9}},
        {'policy_id': 'strict',    'label': 'Strict',     'overrides': {'restrict_threshold': 0.05}},
    ]
})
d = r2.json()['data']
print('BCSE with alts: status', r2.status_code)
print('  is_stub:', d['is_stub'])
print('  divergence_score:', d['divergence_score'])
print('  counterfactuals:', len(d['counterfactual_consequences']))

# Task 1d: BCSE without alternatives -> stub
r3 = client.post('/api/v1/bcse/evaluate', json={
    'agent_id': 'stub-agent',
    'proposed_action_type': 'READ',
    'proposed_resource_scope': '/data/test.csv',
    'session_id': str(uuid4()),
})
d3 = r3.json()['data']
print('BCSE no alts: is_stub:', d3['is_stub'], 'counterfactuals:', len(d3['counterfactual_consequences']))