import pathlib

p = pathlib.Path(r'C:\Users\cathe\OneDrive\Desktop\varynx\varynx\aws\cloudtrail_adapter.py')
src = p.read_text(encoding='utf-8')

# Append scope-limitation docstring improvements to the class docstring and ingest_batch
old_class_doc = '''    Limitations:
    - Does not create or modify CloudTrail trails.
    - Does not assume a trail, S3 destination, or event data store exists.
    - Duplicate detection uses eventID (present in all CloudTrail records).
    - Only AWS management events and supported data events are available.
    '''

new_class_doc = '''    Scope and limitations:
    -----------------------
    * **Instance-scoped deduplication only**: `_ingested_ids` is a per-instance
      in-memory set.  Duplicate suppression is only active within the lifetime of a
      single `CloudTrailAdapter` instance.  A second instance, a restarted process,
      or a new Lambda invocation will re-ingest the same events.  If cross-process
      deduplication is required, store processed `eventID` values externally.

    * **Single AWS account and region**: `LookupEvents` returns events visible to
      the caller's IAM identity in the configured region.  It does **not** cover
      other accounts in an AWS Organization.  For organization-wide coverage, use
      CloudTrail Lake with an organization data store and query via Athena.

    * **Management events only by default**: `LookupEvents` returns management
      events (control-plane API calls).  S3 data events, Lambda invocations, and
      other high-volume data events require a separate trail configuration and are
      **not** returned by this adapter.

    * **10-day lookback limit**: `LookupEvents` returns events from the past 90
      days only (reduced to 10 days for high-volume accounts).  For longer retention,
      a CloudTrail trail must deliver logs to S3.

    * **Not a complete agent-activity monitor**: CloudTrail records AWS API calls
      made by the AWS credentials used by an autonomous agent.  It does **not**
      capture in-process agent behavior, non-AWS network calls, file-system
      operations, or any action that does not result in an AWS API call.

    * **Supplementary evidence only**: Normalized CloudTrail events are labelled
      `source=CLOUDTRAIL` and must never be treated as primary Varynx behavioral
      evidence without additional correlation.

    * Does not create or modify CloudTrail trails.
    * Does not assume a trail, S3 destination, or event data store exists.
    '''

if old_class_doc in src:
    src = src.replace(old_class_doc, new_class_doc, 1)
    p.write_text(src, encoding='utf-8')
    print('cloudtrail_adapter.py: scope docs added')
else:
    print('Pattern not found -- showing current Limitations block:')
    idx = src.find('Limitations:')
    print(repr(src[idx:idx+300]))