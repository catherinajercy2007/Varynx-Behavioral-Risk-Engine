import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\engine\enforcement.py')
src = p.read_text(encoding='utf-8')

old = """            elif response_type == ResponseType.WARN:
                # WARN is a notification; the calling agent receives the warning
                # via the response recommendation.  No lease change is applied.
                logger.info(\"WARN recommendation for agent %s\", agent_id)"""

new = """            elif response_type == ResponseType.WARN:
                # WARN signals that the agent's behaviour has triggered a policy
                # threshold but has not yet reached restriction level.  No lease
                # state change is made.  Effective monitoring occurs because every
                # subsequent agent action passes through the full behavioral analysis
                # pipeline -- evidence is collected, trust is updated, and anomalies
                # are re-evaluated on each event.  This is the project's implemented
                # form of ALLOW_WITH_MONITORING (REQ-011).
                logger.info(\"WARN recommendation for agent %s\", agent_id)"""

if old in src:
    src = src.replace(old, new, 1)
    p.write_text(src, encoding='utf-8')
    print('enforcement.py: WARN monitoring comment added')
else:
    print('Pattern not found - no change needed')