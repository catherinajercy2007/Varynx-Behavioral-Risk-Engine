import pathlib

# 1. Add require_api_key field to VarynxConfig in config.py
p_cfg = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\config.py')
src = p_cfg.read_text(encoding='utf-8')

old = '    api_key: str | None = Field(\n        default=None,\n        description=(\n            "API key for authenticating REST API requests. When set, requests must "\n            "include a matching X-API-Key header. When None (local dev), auth is "\n            "bypassed with a logged warning. Satisfies REQ-016.3."\n        ),\n    )'

new = '    api_key: str | None = Field(\n        default=None,\n        description=(\n            "API key for authenticating REST API requests. When set, requests must "\n            "include a matching X-API-Key header. When None (local dev), auth is "\n            "bypassed with a logged warning. Satisfies REQ-016.3."\n        ),\n    )\n    require_api_key: bool = Field(\n        default=False,\n        description=(\n            "When True, the application will refuse to start if api_key is not set. "\n            "Set VARYNX_REQUIRE_API_KEY=true in production deployments to prevent "\n            "accidentally running without authentication. Does not affect local "\n            "development where api_key is intentionally absent. Satisfies REQ-016.3."\n        ),\n    )'

if old in src:
    src = src.replace(old, new, 1)
    p_cfg.write_text(src, encoding='utf-8')
    print('config.py: require_api_key field added')
else:
    print('PATTERN NOT FOUND in config.py')
    idx = src.find('api_key: str | None')
    print(repr(src[idx:idx+300]))