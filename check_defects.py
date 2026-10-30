import math

# Defect 1: CI half calculation with typical values
history_depth = 5
session_age = 3600.0
horizon_seconds = 3600.0
events_per_second = history_depth / session_age
horizon_events = events_per_second * horizon_seconds
stderr = 0.1
ci_half = 1.96 * stderr * math.sqrt(1.0 + 1.0/history_depth + horizon_events)
print(f"horizon_events={horizon_events:.1f}")
print(f"ci_half={ci_half:.4f}")
print(f"CI for score=0.5: [{max(0.0, 0.5-ci_half):.4f}, {min(1.0, 0.5+ci_half):.4f}]")
print(f"Defect confirmed: CI is always [0.0, 1.0] when horizon_events > 1" if ci_half > 0.5 else "No defect")

# Defect 2: events_per_second with short session
session_age_short = 10.0  # 10 second session
history_depth_short = 3
eps_short = history_depth_short / session_age_short
horizon_events_short = eps_short * horizon_seconds
print(f"\nShort session: events_per_second={eps_short:.3f}, horizon_events={horizon_events_short:.1f}")
print(f"A 10-second session with 3 events projects {horizon_events_short:.0f} events in 1 hour")
print("This is unrealistic for horizon projection")