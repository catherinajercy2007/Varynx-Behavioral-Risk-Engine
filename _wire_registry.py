import pathlib

# 1. Update AWSServiceRegistry to accept optional AWSConfig
p_reg = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\aws\registry.py')
src = p_reg.read_text(encoding='utf-8')

old = "class AWSServiceRegistry:\n    \"\"\"Central registry for all 12 AWS service adapters.\"\"\"\n    def __init__(self) -> None:\n        self.secrets = SecretsManagerAdapter()\n        self.rds = RDSAdapter(secrets_adapter=self.secrets)\n        self.s3 = S3Adapter()\n        self.cloudwatch = CloudWatchAdapter()"
new = """class AWSServiceRegistry:
    \"\"\"Central registry for all 12 AWS service adapters.\"\"\"
    def __init__(self, aws_config=None) -> None:
        self.secrets = SecretsManagerAdapter()
        self.rds = RDSAdapter(secrets_adapter=self.secrets)
        self.s3 = S3Adapter()
        # Use aws_config when provided so the Pydantic-validated flag controls
        # the adapter; fall back to env-var-only construction otherwise.
        if aws_config is not None:
            self.cloudwatch = CloudWatchAdapter.from_aws_config(aws_config)
        else:
            self.cloudwatch = CloudWatchAdapter()"""

if old in src:
    src = src.replace(old, new)
    p_reg.write_text(src, encoding='utf-8')
    print('registry.py updated')
else:
    print('PATTERN NOT FOUND in registry.py; showing current init:')
    idx = src.index('def __init__')
    print(repr(src[idx:idx+300]))