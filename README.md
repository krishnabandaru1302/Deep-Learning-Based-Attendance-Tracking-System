# Attendance Console

A local-first lecture hall attendance system. A scheduled class session has configurable arrival, early-departure, and return grace periods. The backend records timestamped `entry` and `exit` events, derives attendance states, and keeps an event log for the class roster.

> **Research prototype only.** The recognition threshold has not been validated, and this repository contains no benchmark or fairness evaluation. Do not use the system as the sole basis for attendance, access, employment, education, or other consequential decisions.

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
3. A camera worker should identify a face at a configured doorway crossing and send an `entry` or `exit` event to the backend. The event API deduplicates repeated transitions and stores event time, camera id, and match distance.
4. The session policy classifies arrival after `scheduled_start + late_grace_minutes` as late. An exit within `early_leave_grace_minutes` of scheduled end is not marked early. A return within `return_grace_minutes` is treated as a brief break; longer breaks are counted for instructor review.

**The camera worker is not implemented yet.** This build has the session, settings, attendance-state, and event-log APIs, but it does not connect to an RTSP feed or automatically detect doorway crossings. The interface reports the camera as offline and does not claim that attendance is being captured. The existing Haar detector expects one face in an image and is not a whole-room, multi-face camera pipeline.

The app stores face embeddings, session rules, event timestamps, and attendance records in a local SQLite database. Uploaded reference images are processed in memory and not retained. Deleting a participant removes their local records.

## Project structure

```text
backend/app/       FastAPI routes, SQLite storage, model inference, settings
frontend/          Static HTML, CSS, and JavaScript interface
research/          Evaluation protocol and research notes
scripts/           Local setup helpers
models/            Local model weights (excluded from Git)
AAS_v3.ipynb       Original Colab research prototype
```

The backend separates HTTP handling (`main.py`), persistence and event state (`storage.py`), inference (`recognition.py`), and configuration (`settings.py`). The camera worker will be a separate component that emits the documented event contract; it must not write directly to the attendance database.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_PORT` | `8000` | Host port for the local web app when using Compose |
| `ATTENDANCE_DATA_DIR` | `./data` | Location for the SQLite database |
| `VGGFACE_WEIGHTS` | `./models/vgg_face_weights.h5` | Path to authorized pretrained weights |
| `MATCH_DISTANCE_THRESHOLD` | `0.35` | Cosine-distance candidate cutoff inherited from the notebook; unvalidated |
| `CAMERA_RTSP_URL` | unset | Local camera stream source for the future room-camera worker; the current build does not consume the stream |

Do not commit weights, participant images, embeddings, attendance exports, secrets, or private datasets. The `.gitignore` excludes local model and data files.

## Research and limitations

See [`research/README.md`](research/README.md) for an evaluation protocol. No performance results are currently available. Before reporting results, document dataset provenance and consent, held-out splits, preprocessing, model and weight provenance, threshold selection, false acceptance and rejection rates, precision and recall, and uncertainty.

Face embeddings are sensitive biometric data. Obtain informed consent, limit access and retention, provide a non-biometric alternative, and review ambiguous or low-confidence events. This local build is not hardened: it has no instructor authentication or authorization, camera-worker credentials, rate limiting, or deployment security review. Keep it bound to localhost and do not expose its APIs to a network.

## License

No license is currently documented. Add a license before inviting reuse or contributions.
