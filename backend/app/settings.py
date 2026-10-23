from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("ATTENDANCE_DATA_DIR", ROOT / "data")).resolve()
DB_PATH = DATA_DIR / "attendance.sqlite3"
WEIGHTS_PATH = Path(os.getenv("VGGFACE_WEIGHTS", ROOT / "models" / "vgg_face_weights.h5"))
DISTANCE_THRESHOLD = float(os.getenv("MATCH_DISTANCE_THRESHOLD", "0.35"))
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
CAMERA_RTSP_URL = os.getenv("CAMERA_RTSP_URL", "").strip()
CAMERA_ID = os.getenv("CAMERA_ID", "lecture-hall-a-door").strip()
CAMERA_DOOR_LINE_X = min(0.95, max(0.05, float(os.getenv("CAMERA_DOOR_LINE_X", "0.5"))))
CAMERA_ENTRY_DIRECTION = os.getenv("CAMERA_ENTRY_DIRECTION", "right").strip().lower()
CAMERA_SAMPLE_INTERVAL = max(0.1, float(os.getenv("CAMERA_SAMPLE_INTERVAL", "0.5")))
CAMERA_TRACK_TIMEOUT = max(1.0, float(os.getenv("CAMERA_TRACK_TIMEOUT", "4")))
CAMERA_TRACK_MAX_X_GAP = min(0.5, max(0.02, float(os.getenv("CAMERA_TRACK_MAX_X_GAP", "0.15"))))
CAMERA_MATCH_STREAK = max(2, int(os.getenv("CAMERA_MATCH_STREAK", "3")))

