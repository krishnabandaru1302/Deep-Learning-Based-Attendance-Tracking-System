from pathlib import Path
from uuid import uuid4
from math import isfinite
from datetime import datetime, timezone
import json
from importlib.util import find_spec
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from . import storage
from .camera import room_camera
from .recognition import cosine_distance, face_embedding
from .session_engine import record_camera_transition
from .settings import MAX_UPLOAD_BYTES, DISTANCE_THRESHOLD, WEIGHTS_PATH

app = FastAPI(title="Lecture Hall Attendance", version="0.2.0")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
storage.initialize()


@app.on_event("startup")
def start_camera_worker():
    room_camera.start()


@app.on_event("shutdown")
def stop_camera_worker():
    room_camera.stop()


class Review(BaseModel):
    decision: str


class AttendancePolicy(BaseModel):
    late_grace_minutes: int = Field(ge=0, le=120)
    early_leave_grace_minutes: int = Field(ge=0, le=120)
    return_grace_minutes: int = Field(ge=0, le=240)


class SessionCreate(BaseModel):
    class_name: str = Field(min_length=1, max_length=120)
    room_name: str = Field(min_length=1, max_length=120)
    scheduled_start: datetime
    scheduled_end: datetime

    @field_validator("scheduled_start", "scheduled_end")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("Session times must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("Session end must be after session start.")
        return self


class CameraEvent(BaseModel):
    event_id: str = Field(min_length=8, max_length=120)
    person_id: str
    event_type: str
    occurred_at: datetime
    match_distance: float = Field(ge=0, le=1)
    camera_id: str = Field(min_length=1, max_length=120)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("Camera event time must include a timezone.")
        return value


async def read_image(file: UploadFile):
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(415, "Upload a JPEG or PNG image.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image must be 8 MB or smaller.")
    return data


@app.get("/api/health")
def health():
    missing = [name for name in ("cv2", "numpy", "tensorflow") if find_spec(name) is None]
    if missing:
        model_state = "dependencies_missing"
    elif not WEIGHTS_PATH.is_file():
        model_state = "weights_missing"
    else:
        model_state = "ready"
    return {"status": "ok", "model_ready": model_state == "ready", "model_state": model_state}


@app.get("/api/settings/attendance")
def get_attendance_policy():
    return storage.attendance_policy()


@app.get("/api/camera/status")
def camera_status():
    return room_camera.status()


@app.put("/api/settings/attendance")
def set_attendance_policy(policy: AttendancePolicy):
    return storage.update_attendance_policy(policy.model_dump())


@app.post("/api/sessions")
def start_session(request: SessionCreate):
    class_name = request.class_name.strip()
    room_name = request.room_name.strip()
    if not class_name or not room_name:
        raise HTTPException(422, "Class and room names cannot be blank.")
    now = datetime.now(timezone.utc).isoformat()
    session_id = storage.create_session(
        str(uuid4()), class_name, room_name,
        request.scheduled_start.astimezone(timezone.utc).isoformat(),
        request.scheduled_end.astimezone(timezone.utc).isoformat(), now)
    if not session_id:
        raise HTTPException(409, "A class session is already active. End it before starting another.")
    return storage.session_by_id(session_id)


@app.get("/api/sessions/current")
def get_current_session():
    session = storage.current_session()
    return present_session(session)


@app.get("/api/sessions/latest")
def get_latest_session():
    session = storage.latest_session()
    return present_session(session)


def present_session(session):
    if not session:
        return None
    session["policy"] = json.loads(session.pop("policy_json"))
    session["attendance"] = storage.session_attendance(session["id"])
    session["events"] = storage.session_event_log(session["id"], 30)
    return session


@app.post("/api/sessions/{session_id}/end")
def stop_session(session_id: str):
    if not storage.end_session(session_id, datetime.now(timezone.utc).isoformat()):
        raise HTTPException(404, "Active class session not found.")
    return {"id": session_id, "status": "ended"}


@app.post("/api/sessions/{session_id}/events")
def ingest_camera_event(session_id: str, event: CameraEvent):
    try:
        return record_camera_transition(
            session_id, event.event_id, event.person_id, event.event_type,
            event.occurred_at.astimezone(timezone.utc).isoformat(), event.match_distance,
            event.camera_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/sessions/{session_id}/attendance")
def get_session_attendance(session_id: str):
    if not storage.session_by_id(session_id):
        raise HTTPException(404, "Class session not found.")
    return storage.session_attendance(session_id)


@app.get("/api/sessions/{session_id}/events")
def get_session_events(session_id: str):
    if not storage.session_by_id(session_id):
        raise HTTPException(404, "Class session not found.")
    return storage.session_event_log(session_id)


@app.get("/api/people")
def list_people():
    return storage.people()


@app.post("/api/people")
async def enroll(display_name: str = Form(...), consent: bool = Form(False), image: UploadFile = File(...)):
    name = display_name.strip()
    if not name or len(name) > 80:
        raise HTTPException(422, "Name must be between 1 and 80 characters.")
    if not consent:
        raise HTTPException(400, "Participant consent is required before enrollment.")
    try:
        vector = face_embedding(await read_image(image))
        person_id = str(uuid4())
        storage.add_person(person_id, name, vector)
        return {"id": person_id, "display_name": name}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.delete("/api/people/{person_id}")
def remove_person(person_id: str):
    if not storage.delete_person(person_id):
        raise HTTPException(404, "Person not found.")
    return {"deleted": True}


@app.post("/api/matches")
async def match(image: UploadFile = File(...)):
    known = storage.embeddings()
    if not known:
        raise HTTPException(409, "Enroll at least one person before matching.")
    try:
        query = face_embedding(await read_image(image))
        scored = sorted(((cosine_distance(query, vector), pid, name) for pid, name, vector in known))
        distance, person_id, name = scored[0]
        return {"candidate_id": person_id if distance <= DISTANCE_THRESHOLD else None,
                "candidate_name": name if distance <= DISTANCE_THRESHOLD else None,
                "distance": distance, "threshold": DISTANCE_THRESHOLD,
                "requires_human_review": True,
                "message": "Candidate only; review the image and confirm attendance manually."}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/attendance")
def mark_attendance(person_id: str = Form(...), distance: float = Form(...)):
    if not isfinite(distance) or distance < 0 or distance > DISTANCE_THRESHOLD:
        raise HTTPException(422, "The candidate distance is outside the configured cutoff.")
    if not any(p["id"] == person_id for p in storage.people()):
        raise HTTPException(404, "Person not found.")
    record_id = storage.record_attendance(person_id, distance)
    return {"id": record_id, "review_status": "pending"}


@app.get("/api/attendance")
def list_attendance():
    return storage.attendance_records()


@app.patch("/api/attendance/{record_id}/review")
def review_attendance(record_id: int, review: Review):
    if review.decision not in {"confirmed", "rejected"}:
        raise HTTPException(422, "Decision must be confirmed or rejected.")
    if not storage.review_record(record_id, review.decision):
        raise HTTPException(404, "Pending attendance record not found.")
    return {"id": record_id, "review_status": review.decision}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
