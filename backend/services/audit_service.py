import json
from backend.database.db import execute

def audit(session_id, event_type, status="ok", reason=None, order_id=None, metadata=None):
    execute("INSERT INTO audit_events(session_id, order_id, event_type, status, reason, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, order_id, event_type, status, reason, json.dumps(metadata or {})))
