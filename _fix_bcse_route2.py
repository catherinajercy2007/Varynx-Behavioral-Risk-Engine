import pathlib

p = pathlib.Path(r"C:\Users\cathe\OneDrive\Desktop\varynx\varynx\api\routes\bcse.py")
src = p.read_text(encoding="utf-8")

# Patch 1: imports
src = src.replace(
    "from varynx.models.bcse import BCSeContext\n",
    "from varynx.models.bcse import BCSeContext, PolicyAlternative\n"
)

# Patch 2: add alternative_policies to request model (insert after capability_requested line)
src = src.replace(
    "    capability_requested: str = \"evaluate\"\n\n@router",
    "    capability_requested: str = \"evaluate\"\n    # When supplied, Phase 2 engine runs; returns is_stub=False with counterfactuals.\n    # When omitted, Phase 1 stub runs; returns is_stub=True.\n    alternative_policies: list[dict] = []\n\n@router"
)

# Patch 3: pass alternative_policies into BCSeContext
src = src.replace(
    "        \"active_policy_id\": pipeline.response_engine._policy_id,\n    }, strict=False)",
    "        \"active_policy_id\": pipeline.response_engine._policy_id,\n        \"alternative_policies\": [\n            PolicyAlternative.model_validate(a, strict=False).model_dump()\n            for a in body.alternative_policies\n        ],\n    }, strict=False)"
)

p.write_text(src, encoding="utf-8")
print(f"bcse.py updated: {p.stat().st_size} bytes")

# Verify key strings are present
checks = ["alternative_policies", "PolicyAlternative", "counterfactual"]
for c in checks:
    print(c, "in file:", c in src)
