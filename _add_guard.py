import pathlib

# 2. Add startup check in create_app()
p_app = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\api\app.py')
src = p_app.read_text(encoding='utf-8')

old = '    if config is None:\n        config = VarynxConfig()\n\n    app = FastAPI('

new = '    if config is None:\n        config = VarynxConfig()\n\n    # Production auth guard (REQ-016.3): when require_api_key=True the application\n    # must not start without a key.  This is an explicit opt-in so local development\n    # (where api_key is intentionally absent) continues to work unchanged.\n    if config.require_api_key and not config.api_key:\n        raise ValueError(\n            "VARYNX_REQUIRE_API_KEY is True but VARYNX_API_KEY is not set. "\n            "Set VARYNX_API_KEY before starting the application, or set "\n            "VARYNX_REQUIRE_API_KEY=false to allow unauthenticated local access."\n        )\n\n    app = FastAPI('

if old in src:
    src = src.replace(old, new, 1)
    p_app.write_text(src, encoding='utf-8')
    print('app.py: startup auth guard added')
else:
    print('PATTERN NOT FOUND in app.py')
    idx = src.find('if config is None')
    print(repr(src[idx:idx+200]))