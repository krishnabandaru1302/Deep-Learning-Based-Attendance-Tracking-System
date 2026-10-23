# Research Attendance

A local-first attendance research prototype with a web interface and a modular computer-vision backend. It uses a Haar cascade for face detection and a VGGFace descriptor model for candidate matching. Every match is a suggestion and requires human review.

> **Research prototype only.** The recognition threshold has not been validated, and this repository contains no benchmark or fairness evaluation. Do not use the system as the sole basis for attendance, access, employment, education, or other consequential decisions.

## Start the app

### Requirements

- Python 3.10
- VGGFace pretrained weights compatible with the model in `backend/app/recognition.py`
- The weights file `models/vgg_face_weights.h5` (not included in Git)

The original Colab implementation and notebook history are in [`AAS_v3.ipynb`](AAS_v3.ipynb). This web app is a separate modular implementation.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
mkdir -p models
# Configure Kaggle credentials in your shell, then download the original notebook's weights:
pip install kaggle
kaggle datasets download -d acharyarupak391/vggfaceweights --unzip -p models
# Ensure the extracted file is named models/vgg_face_weights.h5
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The weights are not committed. The Kaggle CLI requires an account and authorized API credentials; follow Kaggle's credential setup and keep the credentials outside the repository.

Open <http://127.0.0.1:8000>. Keep the server bound to localhost. The app has no authentication and is not suitable for network exposure or multi-user deployment.

### Workflow

1. Enroll each participant using a consented image containing one clear face.
2. Upload a one-face image to request a candidate match.
3. Review the suggested identity and decide whether to create an attendance entry.
4. Confirm or reject the pending entry in the review queue.

The app stores face embeddings and attendance records in a local SQLite database under `data/`. It does not save uploaded image files. Deleting a participant removes that participant's attendance records and embedding.

## Project structure

```text
backend/app/       FastAPI routes, SQLite storage, model inference, settings
frontend/          Static HTML, CSS, and JavaScript interface
research/          Evaluation protocol and research notes
models/            Local model weights (excluded from Git)
data/              Local embeddings and attendance database (excluded from Git)
AAS_v3.ipynb       Original Colab research prototype
```

The backend separates HTTP handling (`main.py`), persistence (`storage.py`), inference and matching (`recognition.py`), and configuration (`settings.py`).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ATTENDANCE_DATA_DIR` | `./data` | Location for the SQLite database |
| `VGGFACE_WEIGHTS` | `./models/vgg_face_weights.h5` | Path to authorized pretrained weights |
| `MATCH_DISTANCE_THRESHOLD` | `0.35` | Cosine-distance candidate cutoff inherited from the notebook; unvalidated |

Do not commit weights, participant images, embeddings, attendance exports, secrets, or private datasets. The `.gitignore` excludes local model and data files.

## Research and limitations

See [`research/README.md`](research/README.md) for an evaluation protocol. No performance results are currently available. Before reporting results, document dataset provenance and consent, held-out splits, preprocessing, model and weight provenance, threshold selection, false acceptance and rejection rates, precision and recall, and uncertainty.

Face embeddings are sensitive biometric data. Obtain informed consent, limit access and retention, provide a non-biometric alternative, and have a person review every match. This prototype is not hardened: it has no authentication, authorization, audit controls, rate limiting, or deployment security review.

## License

No license is currently documented. Add a license before inviting reuse or contributions.
