# Attendance Console

A local-first lecture hall attendance system. A scheduled class session has configurable arrival, early-departure, and return grace periods. The backend records timestamped `entry` and `exit` events, derives attendance states, and keeps an event log for the class roster.

> **Implementation status: local MVP.** Session rules, event storage, and an initial RTSP camera worker are implemented. Recognition accuracy, doorway tracking, and false-match rates have not been validated on classroom footage. Do not rely on automated marks for official attendance until the camera-specific evaluation, instructor access controls, and a correction process are in place.

## Install with Docker

The Docker Compose setup is the easiest way to run the interface and API together. Install Docker Desktop, then from the repository root:

```bash
cp .env.example .env
python3 -m pip install kaggle
# Configure Kaggle credentials using Kaggle's supported credential setup.
bash scripts/download-model.sh
docker compose up --build
```

Open <http://127.0.0.1:8000>. The service binds to localhost. The model weights are downloaded separately and mounted read-only; they are not included in the repository. The application data persists in a Docker volume. **Do not run `docker compose down -v` unless you intend to permanently delete the local attendance database.**

You can change the local port and candidate cutoff in `.env`. The cutoff defaults to 0.35 from the original notebook and is unvalidated. Keep the default network binding on localhost. The app has no authentication and is not suitable for network exposure or multi-user deployment.

## Run from Python

Python 3.10–3.13 and the same model weights are required. Python 3.13 is recommended for Apple Silicon:

```bash
python3.13 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Download weights with the Kaggle CLI as described above before using recognition. Open <http://127.0.0.1:8000>.

## Current workflow and camera status

1. Add participants and their consented reference photos to the class roster.
2. Set the class name, room, schedule, and timing rules, then start the session.
3. With an RTSP camera and model weights configured, the background camera worker identifies stable face tracks crossing the configured doorway line and records `entry` or `exit` events automatically. The backend deduplicates repeated transitions and stores event time, camera id, and match distance.
4. The session policy classifies arrival after `scheduled_start + late_grace_minutes` as late. An exit within `early_leave_grace_minutes` of scheduled end is not marked early. A return within `return_grace_minutes` is treated as a brief break; longer breaks are counted for instructor review.

The RTSP camera worker and event pipeline are implemented, but have not been validated against a physical classroom camera. Configure a local `CAMERA_RTSP_URL`, install the VGGFace weights, and tune the entrance line and direction before expecting capture. The interface reports the camera as offline until the worker successfully opens the stream. The current face detector/tracker is an initial doorway implementation, not a validated crowded-room identity system; it does not infer presence from a wide seating-area frame.

The app stores face embeddings, session rules, event timestamps, and attendance records in a local SQLite database. Uploaded reference images are processed in memory and not retained. Deleting a participant removes their local records.

## Project structure

```text
backend/app/       FastAPI routes, SQLite storage, camera worker, session engine
frontend/          Static HTML, CSS, and JavaScript interface
research/          Evaluation protocol and research notes
scripts/           Local setup helpers
models/            Local model weights (excluded from Git)
AAS_v3.ipynb       Original Colab research prototype
```

The backend separates HTTP handling (`main.py`), persistence (`storage.py`), face inference (`recognition.py`), the RTSP reader (`camera.py`), session policy (`session_engine.py`), and configuration (`settings.py`). The worker passes events through the session engine rather than writing directly to SQLite.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_PORT` | `8000` | Host port for the local web app when using Compose |
| `ATTENDANCE_DATA_DIR` | `./data` | Location for the SQLite database |
| `VGGFACE_WEIGHTS` | `./models/vgg_face_weights.h5` | Path to authorized pretrained weights |
| `MATCH_DISTANCE_THRESHOLD` | `0.35` | Cosine-distance candidate cutoff inherited from the notebook; unvalidated |
| `CAMERA_RTSP_URL` | unset | Local RTSP stream source consumed by the room-camera worker |
| `CAMERA_ID` | `lecture-hall-a-door` | Identifier included in camera event records |
| `CAMERA_DOOR_LINE_X` | `0.5` | Normalized horizontal crossing line in the camera frame (0–1) |
| `CAMERA_ENTRY_DIRECTION` | `right` | Whether movement to the right or left represents entry into the room |
| `CAMERA_SAMPLE_INTERVAL` | `0.5` | Seconds between analyzed frames |
| `CAMERA_TRACK_TIMEOUT` | `4` | Seconds before a temporarily lost face track is discarded |
| `CAMERA_TRACK_MAX_X_GAP` | `0.15` | Maximum normalized horizontal movement used to associate detections |
| `CAMERA_MATCH_STREAK` | `3` | Consecutive stable matches required before recording a crossing |

Do not commit weights, participant images, embeddings, attendance exports, secrets, or private datasets. The `.gitignore` excludes local model and data files.

## Research and limitations

See [`research/README.md`](research/README.md) for an evaluation protocol. No performance results are currently available. Before reporting results, document dataset provenance and consent, held-out splits, preprocessing, model and weight provenance, threshold selection, false acceptance and rejection rates, precision and recall, and uncertainty.

Face embeddings are sensitive biometric data. Obtain informed consent, limit access and retention, provide a non-biometric alternative, and review ambiguous or low-confidence events. This local build is not hardened: it has no instructor authentication or authorization, camera-worker credentials, rate limiting, or deployment security review. Keep it bound to localhost and do not expose its APIs to a network.

## License

No license is currently documented. Add a license before inviting reuse or contributions.
