"""Session policy and automatic camera-event processing."""
from datetime import datetime, timedelta
from math import isfinite
import json
from . import storage
from .settings import DISTANCE_THRESHOLD


def record_camera_transition(session_id, event_id, person_id, event_type,
                             occurred_at, match_distance, camera_id):
    if event_type not in {"entry", "exit"}:
        raise ValueError("Event type must be entry or exit.")
    if not isfinite(match_distance) or match_distance < 0 or match_distance > DISTANCE_THRESHOLD:
        raise ValueError("Identity match is outside the configured threshold.")
    session = storage.session_by_id(session_id)
    if not session:
        raise LookupError("Class session not found.")
    policy = json.loads(session["policy_json"])
    late_threshold = (datetime.fromisoformat(session["scheduled_start"])
                      + timedelta(minutes=policy["late_grace_minutes"])).isoformat()
    return storage.record_session_event(
        event_id, session_id, person_id, event_type, occurred_at,
        match_distance, camera_id, late_threshold)
