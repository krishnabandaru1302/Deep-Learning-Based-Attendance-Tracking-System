# Room attendance architecture

## Runtime flow

```text
RTSP room camera
      │
      ▼
Camera worker ── face detection + short-lived track association
      │           + doorway crossing state machine
      │
      ├── recognized crossing: person id, entry/exit, event time,
      │                         match distance, camera id, event id
      ▼
FastAPI session event API
      ▼
Attendance state engine ── SQLite session roster + append-only event log
      ▼
Instructor console ── current presence, late arrivals, away/returned,
                       entry/exit timestamps, session audit trail
```

The camera worker currently runs in a background thread in the FastAPI process. It owns video decoding and frame analysis; the session engine owns timing rules, idempotency, and attendance state. The worker calls the session engine rather than writing to SQLite directly. The HTTP event endpoint is also available for a future isolated worker process.

## Camera placement

For reliable entry and exit events, the camera must see the entrance and provide a useful face view while a student crosses a configured line or zone. A high, wide corner view of the whole lecture hall can show occupancy but often hides faces, overlaps students, or loses them behind seats. If a single corner camera cannot see both the doorway crossing and a face clearly, use a dedicated entrance camera or another consented attendance method. The current UI diagram is a setup guide, not a live camera view.

The current worker:

1. Read an RTSP source from server-side configuration; never return its URL or credentials to the browser.
2. Decode frames in memory and detect multiple faces within a doorway region of interest.
3. Associate detections into short-lived tracks so one person standing near the line does not generate repeated events.
4. Require a stable identity across more than one frame, then detect direction across the configured entrance boundary.
5. Emit one idempotent event per crossing with a unique event id, event time, camera id, matched person id, and match distance.
6. Skip faces outside the configured identity threshold rather than create a guessed identity event.

This is an initial baseline, not a validated crowded-room identity system. It uses Haar face boxes, VGGFace embeddings, and simple horizontal centroid tracking; it has not been tested with the target camera, hallway crowding, lighting, or occlusion. Its match threshold is inherited from the notebook and unvalidated. The entrance region, more robust person tracking, and camera-specific calibration still need field evaluation.

## Session and grace rules

The `attendance_policy` table stores the instructor's current defaults:

- `late_grace_minutes` (default 10): time after scheduled start that still counts as on time.
- `early_leave_grace_minutes` (default 5): time before scheduled end that is acceptable when the final exit is recorded.
- `return_grace_minutes` (default 10): an exit followed by re-entry within this time is logged as a brief break; longer breaks are counted separately.

When a class starts, its policy is copied into `sessions.policy_json`. Later preference changes apply to the next class, so an in-progress class cannot change classification retroactively. The event ledger stores entry/exit timestamps independently from the derived session status. Late arrival and break information remain visible even when a student later returns.

The backend endpoints are:

- `GET/PUT /api/settings/attendance` — read or change future-session policy.
- `POST /api/sessions`, `GET /api/sessions/current`, `POST /api/sessions/{id}/end` — manage class sessions.
- `POST /api/sessions/{id}/events` — accept one recognized `entry`/`exit` transition from an external worker; the in-process camera thread uses the same session engine directly.
- `GET /api/sessions/{id}/attendance` and `GET /api/sessions/{id}/events` — read the roster state and event ledger.

Example worker event:

```json
{
  "event_id": "camera-a-track-918-entry-20261024T081501Z",
  "person_id": "participant-id",
  "event_type": "entry",
  "occurred_at": "2026-10-24T08:15:01Z",
  "match_distance": 0.21,
  "camera_id": "lecture-hall-a-door"
}
```

## Implementation status

Session creation, policy persistence, event deduplication, transition state, attendance summaries, the RTSP capture loop, face detection, short track association, and the operational web console are implemented. The camera worker has not been validated on physical camera footage, and the face matcher and threshold remain unvalidated. Instructor authentication and camera-worker request authentication are not implemented. The interface distinguishes an open camera stream from recognition readiness; it must not claim attendance capture when model weights are missing or tracking is stopped. Compose binds to localhost; keep it that way.
