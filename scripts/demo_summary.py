"""Pretty-print the demo's call log and recordings from stdin JSON. Used by demo.sh."""
import json
import sys

kind = sys.argv[1]
rows = json.load(sys.stdin)
if kind == "calls":
    for c in rows:
        who = c.get("feature_kind") or f"contact#{c.get('contact_id')}"
        secs = c.get("duration_seconds") or 0
        print(f"  {c['started_at'][11:19]}  {c['direction']:8} {who:15} {c['outcome']:22} {secs:>4}s  rec={c.get('recording_id')}")
else:
    for r in rows:
        print(f"  #{r['id']} {r['kind']:9} {r['duration_seconds'] or 0:>4}s  {r['audio_url']}")
