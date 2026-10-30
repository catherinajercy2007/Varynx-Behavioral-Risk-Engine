import pathlib, re

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\engine\pipeline.py')
src = p.read_text(encoding='utf-8')

# Find the __init__ where cloudwatch_adapter is assigned
old = "        # Optional CloudWatch integration. Never required for core operation.\n        self._cloudwatch = cloudwatch_adapter"

new = """        # Optional CloudWatch integration. Never required for core operation.
        # If caller passes an adapter explicitly, use it.
        # Otherwise, auto-create from config when cloudwatch_enabled=True.
        if cloudwatch_adapter is not None:
            self._cloudwatch = cloudwatch_adapter
        elif self.config.aws.cloudwatch_enabled:
            try:
                from varynx.aws.cloudwatch_adapter import CloudWatchAdapter as _CW
                self._cloudwatch = _CW.from_aws_config(self.config.aws)
            except Exception:
                self._cloudwatch = None
        else:
            self._cloudwatch = None"""

if old in src:
    src = src.replace(old, new, 1)
    p.write_text(src, encoding='utf-8')
    print('pipeline.py updated')
else:
    print('PATTERN NOT FOUND; showing context:')
    idx = src.find('cloudwatch_adapter')
    print(repr(src[max(0,idx-100):idx+200]))