"""Clear all tracking data from the database, preserving the schema."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "tracking.db"

if not db_path.exists():
    print("No database found — nothing to clear.")
else:
    conn = sqlite3.connect(str(db_path))
    tables = [
        "track_step_velocities", "track_avg_velocities",
        "points", "events", "cells", "frames", "runs", "pipeline_state",
    ]
    conn.execute("PRAGMA foreign_keys = OFF")
    for t in tables:
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()
    conn.close()
    print("Database cleared. Schema intact.")
