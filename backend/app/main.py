from pathlib import Path
from uuid import uuid4
from math import isfinite
from importlib.util import find_spec
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import storage
from .recognition import cosine_distance, face_embedding
from .settings import MAX_UPLOAD_BYTES, DISTANCE_THRESHOLD, WEIGHTS_PATH

app = FastAPI(title="Research Attendance", version="0.1.0")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
storage.initialize()


class Review(BaseModel):
    decision: str


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
