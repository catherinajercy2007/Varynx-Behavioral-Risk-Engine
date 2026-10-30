import os; os.environ['VARYNX_DATABASE_URL']='memory://'
from varynx.config import VarynxConfig
from varynx.api.app import create_app

# Case 1: production guard - require_api_key=True, no key -> should raise
try:
    cfg = VarynxConfig(database_url='memory://', require_api_key=True)
    create_app(config=cfg)
    print('FAIL: should have raised')
except ValueError as e:
    print('PASS: startup refused when require_api_key=True and no key:', str(e)[:80])

# Case 2: require_api_key=True + key set -> should succeed
cfg2 = VarynxConfig(database_url='memory://', require_api_key=True, api_key='test-key')
app2 = create_app(config=cfg2)
print('PASS: startup succeeds when require_api_key=True and key is set')

# Case 3: default (dev mode) -> no key, no error
cfg3 = VarynxConfig(database_url='memory://')
app3 = create_app(config=cfg3)
print('PASS: dev mode (no key) starts without error (warning expected)')

# Check CORS includes 3001
print('CORS origins:', cfg3.cors_origin_list)