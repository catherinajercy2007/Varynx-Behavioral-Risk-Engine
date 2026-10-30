import math

# Short session CI defect
history_depth = 3
session_age = 10.0  # 10 seconds
stderr = 0.05
horizon_seconds = 3600.0
events_per_second = history_depth / session_age
horizon_events = events_per_second * horizon_seconds
ci_half = 1.96 * stderr * math.sqrt(1.0 + 1.0/history_depth + horizon_events)
ci_lower = max(0.0, 0.5 - ci_half)
ci_upper = min(1.0, 0.5 + ci_half)
print(f"history_depth={history_depth}, session_age={session_age}s")
print(f"horizon_events={horizon_events:.1f}")
print(f"ci_half={ci_half:.4f}")
print(f"CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
print(f"Defect: CI is [{ci_lower},{ci_upper}] = always [0,1] for short sessions" if ci_lower == 0.0 and ci_upper == 1.0 else "OK")

# Also check: pipeline exception scope
# The CW publish is inside the outer try block
# If publish_pipeline_result raises, it's caught by inner try/except
# Then outer except also runs -- but result.error should NOT be set
# because inner exception was already caught
print()
print("Pipeline CW scope: inner try catches CW exceptions before outer try sees them")
print("But if inner try is missing on CW call, outer catch would set result.error")