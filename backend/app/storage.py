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
        """)


def add_person(person_id, display_name, embedding):
    with connect() as db:
        db.execute("INSERT INTO people VALUES (?, ?, ?, ?)",
                   (person_id, display_name, json.dumps(embedding), datetime.now(timezone.utc).isoformat()))


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
