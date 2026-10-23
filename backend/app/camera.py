"""Local RTSP worker for doorway face tracks and entry/exit transitions.

Frames remain in memory. The worker emits attendance events only after a stable
identity is tracked across several sampled frames and crosses the door line.
"""
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4
from importlib.util import find_spec
from . import storage
from .recognition import cosine_distance, face_embedding
from .session_engine import record_camera_transition
from .settings import (CAMERA_DOOR_LINE_X, CAMERA_ENTRY_DIRECTION,
                       CAMERA_ID, CAMERA_MATCH_STREAK, CAMERA_RTSP_URL,
                       CAMERA_SAMPLE_INTERVAL, CAMERA_TRACK_MAX_X_GAP, CAMERA_TRACK_TIMEOUT,
                       DISTANCE_THRESHOLD, WEIGHTS_PATH)


class RoomCameraWorker:
    def __init__(self):
        self._lock = Lock()
        self._stop = Event()
        self._thread = None
        self._state = {
            "connected": False,
            "source_configured": bool(CAMERA_RTSP_URL),
            "worker_available": False,
            "status": "not_configured" if not CAMERA_RTSP_URL else "connecting",
            "camera_id": CAMERA_ID,
            "last_frame_at": None,
            "last_error": None,
        }

    def status(self):
        with self._lock:
            return dict(self._state)

    def _set(self, **updates):
        with self._lock:
            self._state.update(updates)

    def start(self):
        if not CAMERA_RTSP_URL:
            return
        if any(find_spec(name) is None for name in ("cv2", "numpy", "tensorflow")):
            self._set(status="dependencies_missing", last_error="Camera recognition dependencies are not installed.")
            return
        import cv2  # noqa: F401
        self._stop.clear()
        self._set(worker_available=True, status="connecting", last_error=None)
        self._thread = Thread(target=self._guarded_run, name="room-camera-worker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _guarded_run(self):
        while not self._stop.is_set():
            try:
                self._run()
            except Exception as exc:
                self._set(connected=False, status="worker_error",
                          last_error=f"Camera worker stopped unexpectedly ({type(exc).__name__}).")
                self._stop.wait(3)

    def _run(self):
        import cv2

        tracks = {}
        next_track_id = 1
        last_sample = 0.0
        known = []
        known_refresh = 0.0
        while not self._stop.is_set():
            capture = cv2.VideoCapture(CAMERA_RTSP_URL, cv2.CAP_FFMPEG)
            if not capture.isOpened():
                self._set(connected=False, status="camera_unreachable", last_error="Could not open the configured camera stream.")
                capture.release()
                self._stop.wait(3)
                continue
            self._set(connected=True, worker_available=True, status="monitoring", last_error=None)
            detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if detector.empty():
                self._set(connected=False, status="detector_unavailable", last_error="OpenCV face detector could not be loaded.")
                capture.release()
                self._stop.wait(5)
                continue
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    self._set(connected=False, status="stream_interrupted", last_error="Camera stream stopped; reconnecting.")
                    break
                now = monotonic()
                if now - last_sample < CAMERA_SAMPLE_INTERVAL:
                    continue
                last_sample = now
                self._set(last_frame_at=datetime.now(timezone.utc).isoformat())
                session = storage.current_session()
                if not session:
                    tracks.clear()
                    continue
                if not WEIGHTS_PATH.is_file():
                    tracks.clear()
                    self._set(status="camera_connected_model_missing", last_error="Recognition weights are not installed.")
                    continue
                self._set(status="monitoring", last_error=None)
                if now - known_refresh > 30:
                    known = storage.embeddings()
                    known_refresh = now
                height, width = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                boxes = detector.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(64, 64))
                observed = []
                for x, y, w, h in boxes:
                    margin_x, margin_y = int(w * .2), int(h * .2)
                    x0, y0 = max(0, x-margin_x), max(0, y-margin_y)
                    x1, y1 = min(width, x+w+margin_x), min(height, y+h+margin_y)
                    crop = frame[y0:y1, x0:x1]
                    encoded, image = cv2.imencode(".jpg", crop)
                    if not encoded:
                        continue
                    try:
                        vector = face_embedding(image.tobytes())
                    except (ValueError, RuntimeError):
                        continue
                    if not known:
                        continue
                    scores = sorted((cosine_distance(vector, saved), person_id, name) for person_id, name, saved in known)
                    distance, person_id, _ = scores[0]
                    if distance <= DISTANCE_THRESHOLD:
                        observed.append(((x + w / 2) / width, person_id, distance))
                tracks, next_track_id = self._update_tracks(
                    tracks, observed, next_track_id, now, CAMERA_TRACK_TIMEOUT, width,
                    CAMERA_TRACK_MAX_X_GAP)
                line = CAMERA_DOOR_LINE_X
                room_side = "right" if CAMERA_ENTRY_DIRECTION == "right" else "left"
                for track in tracks.values():
                    current_side = "right" if track["x"] >= line else "left"
                    if track["streak"] >= CAMERA_MATCH_STREAK and current_side != track["event_side"]:
                        event_type = "entry" if current_side == room_side else "exit"
                        event_id = f"{CAMERA_ID}-{track['id']}-{event_type}-{uuid4().hex[:12]}"
                        try:
                            record_camera_transition(
                                session["id"], event_id, track["person_id"], event_type,
                                datetime.now(timezone.utc).isoformat(), track["distance"], CAMERA_ID)
                            track["event_side"] = current_side
                        except (LookupError, ValueError):
                            # Invalid transitions (for example, an exit without a
                            # recorded entry) are not converted into attendance.
                            track["event_side"] = current_side
            capture.release()
            tracks.clear()
            if not self._stop.is_set():
                self._stop.wait(2)
        self._set(connected=False, status="stopped")

    @staticmethod
    def _update_tracks(tracks, observed, next_id, now, timeout, frame_width, max_x_gap=.15):
        tracks = {key: value for key, value in tracks.items() if now - value["seen"] <= timeout}
        used = set()
        max_gap = max(max_x_gap, 100 / max(frame_width, 1))
        for x, person_id, distance in observed:
            choices = [(abs(track["x"]-x), key, track) for key, track in tracks.items()
                       if key not in used and track["person_id"] == person_id and abs(track["x"]-x) <= max_gap]
            if choices:
                _, key, track = min(choices, key=lambda item: item[0])
                if track["candidate_id"] == person_id:
                    track["streak"] += 1
                else:
                    track["candidate_id"] = person_id
                    track["streak"] = 1
                track["x"], track["seen"], track["distance"] = x, now, distance
                used.add(key)
            else:
                key = next_id
                next_id += 1
                tracks[key] = {"id": key, "person_id": person_id, "candidate_id": person_id,
                               "streak": 1, "x": x, "seen": now, "distance": distance,
                               "event_side": "right" if x >= CAMERA_DOOR_LINE_X else "left"}
                used.add(key)
        return tracks, next_id


room_camera = RoomCameraWorker()
