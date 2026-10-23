# Research Attendance

A local-first attendance research prototype with a web interface and a modular computer-vision backend. It uses a Haar cascade for face detection and a VGGFace descriptor model for candidate matching. Every match is a suggestion and requires human review.

> **Research prototype only.** The recognition threshold has not been validated, and this repository contains no benchmark or fairness evaluation. Do not use the system as the sole basis for attendance, access, employment, education, or other consequential decisions.

## Install with Docker

The Docker Compose setup is the easiest way to run the interface and API together. Install Docker Desktop, then from the repository root:

```bash
cp .env.example .env
python3 -m pip install kaggle
# Configure Kaggle credentials using Kaggle's supported credential setup.
./scripts/download-model.sh
docker compose up --build
```

Open <http://127.0.0.1:8000>. The service binds to localhost. The model weights are downloaded separately and mounted read-only; they are not included in the repository. The application data persists in a Docker volume. **Do not run `docker compose down -v` unless you intend to permanently delete the local attendance database.**

You can change the local port and candidate cutoff in `.env`. The cutoff defaults to 0.35 from the original notebook and is unvalidated. Keep the default network binding on localhost. The app has no authentication and is not suitable for network exposure or multi-user deployment.

## Run from Python

Python 3.10 and the same model weights are required:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Download weights with the Kaggle CLI as described above before using recognition. Open <http://127.0.0.1:8000>.

## Workflow

1. Enroll each participant using a consented image containing one clear face.
2. Upload a one-face image to request a candidate match.
3. Review the displayed image and suggested identity before sending a candidate to the attendance review queue.
4. Confirm or reject the pending entry in the queue.

The app stores face embeddings and attendance records in a local SQLite database. It does not save uploaded image files. Deleting a participant removes that participant's attendance records and embedding.

## Project structure

```text
backend/app/       FastAPI routes, SQLite storage, model inference, settings
frontend/          Static HTML, CSS, and JavaScript interface
research/          Evaluation protocol and research notes
scripts/           Local setup helpers
models/            Local model weights (excluded from Git)
AAS_v3.ipynb       Original Colab research prototype
```

The backend separates HTTP handling (`main.py`), persistence (`storage.py`), inference and matching (`recognition.py`), and configuration (`settings.py`).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_PORT` | `8000` | Host port for the local web app when using Compose |
| `ATTENDANCE_DATA_DIR` | `./data` | Location for the SQLite database |
| `VGGFACE_WEIGHTS` | `./models/vgg_face_weights.h5` | Path to authorized pretrained weights |
| `MATCH_DISTANCE_THRESHOLD` | `0.35` | Cosine-distance candidate cutoff inherited from the notebook; unvalidated |

Do not commit weights, participant images, embeddings, attendance exports, secrets, or private datasets. The `.gitignore` excludes local model and data files.

## Research and limitations

See [`research/README.md`](research/README.md) for an evaluation protocol. No performance results are currently available. Before reporting results, document dataset provenance and consent, held-out splits, preprocessing, model and weight provenance, threshold selection, false acceptance and rejection rates, precision and recall, and uncertainty.

Face embeddings are sensitive biometric data. Obtain informed consent, limit access and retention, provide a non-biometric alternative, and have a person review every match. This prototype is not hardened: it has no authentication, authorization, audit controls, rate limiting, or deployment security review.

## License

No license is currently documented. Add a license before inviting reuse or contributions.
