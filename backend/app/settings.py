from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("ATTENDANCE_DATA_DIR", ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "attendance.sqlite3"
WEIGHTS_PATH = Path(os.getenv("VGGFACE_WEIGHTS", ROOT / "models" / "vgg_face_weights.h5"))
DISTANCE_THRESHOLD = float(os.getenv("MATCH_DISTANCE_THRESHOLD", "0.35"))
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

