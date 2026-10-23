import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .settings import DATA_DIR, DB_PATH


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS people (
          id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
          embedding TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attendance (
          id INTEGER PRIMARY KEY AUTOINCREMENT, person_id TEXT NOT NULL,
          observed_at TEXT NOT NULL, distance REAL NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'pending',
          FOREIGN KEY(person_id) REFERENCES people(id)
        );
        CREATE TABLE IF NOT EXISTS attendance_policy (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          late_grace_minutes INTEGER NOT NULL DEFAULT 10,
          early_leave_grace_minutes INTEGER NOT NULL DEFAULT 5,
          return_grace_minutes INTEGER NOT NULL DEFAULT 10
        );
        INSERT OR IGNORE INTO attendance_policy (id) VALUES (1);
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY,
          class_name TEXT NOT NULL,
          room_name TEXT NOT NULL,
          scheduled_start TEXT NOT NULL,
          scheduled_end TEXT NOT NULL,
          started_at TEXT NOT NULL,
          ended_at TEXT,
          status TEXT NOT NULL,
          policy_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sessions_status_idx ON sessions(status, started_at);
        CREATE TABLE IF NOT EXISTS session_attendance (
          session_id TEXT NOT NULL,
          person_id TEXT NOT NULL,
          first_entry_at TEXT,
          last_event_at TEXT,
          last_event_type TEXT,
          status TEXT NOT NULL,
          late_by_minutes INTEGER NOT NULL DEFAULT 0,
          away_since TEXT,
          total_away_seconds INTEGER NOT NULL DEFAULT 0,
          long_breaks INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (session_id, person_id),
          FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
          FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS session_events (
          event_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          person_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          match_distance REAL NOT NULL,
          camera_id TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE,
          FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS session_events_order_idx ON session_events(session_id, occurred_at);
        """)


def attendance_policy():
    with connect() as db:
        return dict(db.execute("SELECT late_grace_minutes, early_leave_grace_minutes, return_grace_minutes FROM attendance_policy WHERE id = 1").fetchone())


def update_attendance_policy(policy):
    with connect() as db:
        db.execute("UPDATE attendance_policy SET late_grace_minutes = ?, early_leave_grace_minutes = ?, return_grace_minutes = ? WHERE id = 1",
                   (policy["late_grace_minutes"], policy["early_leave_grace_minutes"], policy["return_grace_minutes"]))
        return dict(db.execute("SELECT late_grace_minutes, early_leave_grace_minutes, return_grace_minutes FROM attendance_policy WHERE id = 1").fetchone())


def create_session(session_id, class_name, room_name, scheduled_start, scheduled_end, started_at):
    with connect() as db:
        active = db.execute("SELECT id FROM sessions WHERE status = 'active'").fetchone()
        if active:
            return None
        policy = dict(db.execute("SELECT late_grace_minutes, early_leave_grace_minutes, return_grace_minutes FROM attendance_policy WHERE id = 1").fetchone())
        db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, NULL, 'active', ?)",
                   (session_id, class_name, room_name, scheduled_start, scheduled_end, started_at, json.dumps(policy)))
        db.execute("INSERT INTO session_attendance (session_id, person_id, status) SELECT ?, id, 'absent' FROM people", (session_id,))
        return session_id


def current_session():
    with connect() as db:
        row = db.execute("SELECT * FROM sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def latest_session():
    with connect() as db:
        row = db.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def session_by_id(session_id):
    with connect() as db:
        row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None


def end_session(session_id, ended_at):
    with connect() as db:
        session = db.execute("SELECT * FROM sessions WHERE id = ? AND status = 'active'", (session_id,)).fetchone()
        if not session:
            return False
        policy = json.loads(session["policy_json"])
        end_time = datetime.fromisoformat(session["scheduled_end"])
        early_cutoff = end_time.timestamp() - policy["early_leave_grace_minutes"] * 60
        rows = db.execute("SELECT person_id, status, away_since FROM session_attendance WHERE session_id = ?", (session_id,)).fetchall()
        for row in rows:
            if row["away_since"] and datetime.fromisoformat(row["away_since"]).timestamp() < early_cutoff:
                status = "left_early"
            elif row["status"] == "away":
                late = db.execute("SELECT late_by_minutes FROM session_attendance WHERE session_id = ? AND person_id = ?", (session_id, row["person_id"])).fetchone()[0]
                status = "late" if late else "present"
            else:
                status = row["status"]
            db.execute("UPDATE session_attendance SET status = ?, away_since = NULL WHERE session_id = ? AND person_id = ?",
                       (status, session_id, row["person_id"]))
        db.execute("UPDATE sessions SET status = 'ended', ended_at = ? WHERE id = ?", (ended_at, session_id))
        return True


def record_session_event(event_id, session_id, person_id, event_type, occurred_at, match_distance, camera_id, late_threshold):
    with connect() as db:
        if db.execute("SELECT 1 FROM session_events WHERE event_id = ?", (event_id,)).fetchone():
            return {"duplicate": True}
        session = db.execute("SELECT status FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            raise LookupError("Class session not found.")
        if session["status"] != "active":
            raise ValueError("This class session is not active.")
        if not db.execute("SELECT 1 FROM people WHERE id = ?", (person_id,)).fetchone():
            raise LookupError("Participant not found.")
        current = db.execute("SELECT * FROM session_attendance WHERE session_id = ? AND person_id = ?", (session_id, person_id)).fetchone()
        if event_type == "exit" and (not current or not current["first_entry_at"]):
            raise ValueError("An exit event needs a previous entry event.")
        if current and current["last_event_at"] and datetime.fromisoformat(occurred_at) < datetime.fromisoformat(current["last_event_at"]):
            raise ValueError("Camera events must arrive in timestamp order for each participant.")
        if current and current["first_entry_at"] and current["last_event_type"] == event_type:
            return {"duplicate": True, "status": current["status"]}
        db.execute("INSERT INTO session_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (event_id, session_id, person_id, event_type, occurred_at, match_distance, camera_id))
        if event_type == "entry":
            if not current or not current["first_entry_at"]:
                observed = datetime.fromisoformat(occurred_at).timestamp()
                threshold = datetime.fromisoformat(late_threshold).timestamp()
                late_by = max(0, int((observed - threshold + 59) // 60))
                status = "late" if late_by else "present"
                db.execute("UPDATE session_attendance SET first_entry_at = ?, last_event_at = ?, last_event_type = 'entry', status = ?, late_by_minutes = ? WHERE session_id = ? AND person_id = ?",
                           (occurred_at, occurred_at, status, late_by, session_id, person_id))
            else:
                away_seconds = max(0, int((datetime.fromisoformat(occurred_at) - datetime.fromisoformat(current["away_since"])).total_seconds())) if current["away_since"] else 0
                policy = json.loads(db.execute("SELECT policy_json FROM sessions WHERE id = ?", (session_id,)).fetchone()[0])
                long_break = int(away_seconds > policy["return_grace_minutes"] * 60)
                status = "late" if current["late_by_minutes"] else "present"
                db.execute("UPDATE session_attendance SET last_event_at = ?, last_event_type = 'entry', status = ?, away_since = NULL, total_away_seconds = total_away_seconds + ?, long_breaks = long_breaks + ? WHERE session_id = ? AND person_id = ?",
                           (occurred_at, status, away_seconds, long_break, session_id, person_id))
        else:
            db.execute("UPDATE session_attendance SET last_event_at = ?, last_event_type = 'exit', status = 'away', away_since = ? WHERE session_id = ? AND person_id = ?",
                       (occurred_at, occurred_at, session_id, person_id))
        row = db.execute("SELECT status, first_entry_at, late_by_minutes, away_since, total_away_seconds, long_breaks FROM session_attendance WHERE session_id = ? AND person_id = ?",
                         (session_id, person_id)).fetchone()
        return {"duplicate": False, **dict(row)}


def session_attendance(session_id):
    with connect() as db:
        rows = db.execute("""
          SELECT p.id AS person_id, p.display_name, sa.first_entry_at, sa.last_event_at,
                 sa.last_event_type, sa.status, sa.late_by_minutes, sa.away_since,
                 sa.total_away_seconds, sa.long_breaks
          FROM session_attendance sa JOIN people p ON p.id = sa.person_id
          WHERE sa.session_id = ? ORDER BY p.display_name
        """, (session_id,)).fetchall()
        return [dict(row) for row in rows]


def session_event_log(session_id, limit=100):
    with connect() as db:
        rows = db.execute("""
          SELECT e.event_id, e.person_id, p.display_name, e.event_type, e.occurred_at,
                 e.match_distance, e.camera_id
          FROM session_events e JOIN people p ON p.id = e.person_id
          WHERE e.session_id = ? ORDER BY e.occurred_at DESC LIMIT ?
        """, (session_id, limit)).fetchall()
        return [dict(row) for row in rows]


def add_person(person_id, display_name, embedding):
    with connect() as db:
        db.execute("INSERT INTO people VALUES (?, ?, ?, ?)",
                   (person_id, display_name, json.dumps(embedding), datetime.now(timezone.utc).isoformat()))
        active = db.execute("SELECT id FROM sessions WHERE status = 'active' LIMIT 1").fetchone()
        if active:
            db.execute("INSERT OR IGNORE INTO session_attendance (session_id, person_id, status) VALUES (?, ?, 'absent')",
                       (active["id"], person_id))


def people():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT id, display_name, created_at FROM people ORDER BY display_name")]


def embeddings():
    with connect() as db:
        return [(row["id"], row["display_name"], json.loads(row["embedding"]))
                for row in db.execute("SELECT id, display_name, embedding FROM people")]


def delete_person(person_id):
    with connect() as db:
        db.execute("DELETE FROM attendance WHERE person_id = ?", (person_id,))
        return db.execute("DELETE FROM people WHERE id = ?", (person_id,)).rowcount > 0


def record_attendance(person_id, distance):
    with connect() as db:
        cur = db.execute("INSERT INTO attendance (person_id, observed_at, distance) VALUES (?, ?, ?)",
                         (person_id, datetime.now(timezone.utc).isoformat(), distance))
        return cur.lastrowid


def attendance_records():
    with connect() as db:
        return [dict(row) for row in db.execute("""
          SELECT a.id, p.display_name, a.observed_at, a.distance, a.review_status
          FROM attendance a JOIN people p ON p.id = a.person_id ORDER BY a.observed_at DESC LIMIT 100
        """)]


def review_record(record_id, status):
    with connect() as db:
        return db.execute("UPDATE attendance SET review_status = ? WHERE id = ? AND review_status = 'pending'",
                          (status, record_id)).rowcount > 0
