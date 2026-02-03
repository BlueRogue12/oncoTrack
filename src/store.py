"""
SQLite persistence layer for cell tracking data.
Handles schema creation, CRUD operations, and queries.
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TrackingStore:
    """SQLite database manager for incremental cell tracking."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Frames table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS frames (
                    frame_index INTEGER PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    source_path TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Cells table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cells (
                    cell_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    first_frame INTEGER NOT NULL,
                    last_frame INTEGER,
                    FOREIGN KEY (first_frame) REFERENCES frames(frame_index)
                )
            """)
            
            # Points table (cell positions)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS points (
                    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cell_id INTEGER NOT NULL,
                    frame_index INTEGER NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    quality REAL,
                    units TEXT DEFAULT 'pixel',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cell_id) REFERENCES cells(cell_id),
                    FOREIGN KEY (frame_index) REFERENCES frames(frame_index),
                    UNIQUE(cell_id, frame_index)
                )
            """)
            
            # Events table (divisions, merges, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    parent_cell_id INTEGER,
                    child_cell_id INTEGER,
                    frame_index INTEGER NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_cell_id) REFERENCES cells(cell_id),
                    FOREIGN KEY (child_cell_id) REFERENCES cells(cell_id),
                    FOREIGN KEY (frame_index) REFERENCES frames(frame_index)
                )
            """)
            
            # Runs table (tracking run metadata)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    batch_id TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    xml_path TEXT,
                    csv_paths_json TEXT,
                    frame_range_start INTEGER,
                    frame_range_end INTEGER,
                    status TEXT DEFAULT 'running'
                )
            """)
            
            # Pipeline state table (for finalized frame tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indices for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_points_cell ON points(cell_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_points_frame ON points(frame_index)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_frame ON events(frame_index)")
            
            logger.info(f"Database schema initialized at {self.db_path}")
    
    # Frame operations
    def add_frame(self, frame_index: int, timestamp: float, source_path: str):
        """Add a new frame to the database."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO frames (frame_index, timestamp, source_path) VALUES (?, ?, ?)",
                (frame_index, timestamp, source_path)
            )
            logger.debug(f"Added frame {frame_index}")
    
    def get_frame(self, frame_index: int) -> Optional[Dict[str, Any]]:
        """Get frame information."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM frames WHERE frame_index = ?", (frame_index,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_max_frame_index(self) -> Optional[int]:
        """Get the maximum frame index in the database."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT MAX(frame_index) as max_idx FROM frames").fetchone()
            return row['max_idx'] if row['max_idx'] is not None else None
    
    # Cell operations
    def create_cell(self, first_frame: int) -> int:
        """Create a new cell and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO cells (first_frame) VALUES (?)",
                (first_frame,)
            )
            cell_id = cursor.lastrowid
            logger.info(f"Created new cell {cell_id} at frame {first_frame}")
            return cell_id
    
    def update_cell_last_frame(self, cell_id: int, last_frame: int):
        """Update the last frame for a cell."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE cells SET last_frame = ? WHERE cell_id = ?",
                (last_frame, cell_id)
            )
    
    def get_cell(self, cell_id: int) -> Optional[Dict[str, Any]]:
        """Get cell information."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM cells WHERE cell_id = ?", (cell_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_all_cells(self) -> List[Dict[str, Any]]:
        """Get all cells."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM cells ORDER BY cell_id").fetchall()
            return [dict(row) for row in rows]
    
    # Point operations
    def add_points(self, points: List[Dict[str, Any]]):
        """
        Add multiple points to the database.
        Each point dict should have: cell_id, frame_index, x, y, quality (optional), units
        """
        with self.get_connection() as conn:
            for point in points:
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO points 
                           (cell_id, frame_index, x, y, quality, units) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            point['cell_id'],
                            point['frame_index'],
                            point['x'],
                            point['y'],
                            point.get('quality'),
                            point.get('units', 'pixel')
                        )
                    )
                except sqlite3.IntegrityError as e:
                    logger.error(f"Failed to add point: {point}, error: {e}")
            logger.info(f"Added {len(points)} points")
    
    def get_cell_points(self, cell_id: int, frame_range: Optional[Tuple[int, int]] = None) -> List[Dict[str, Any]]:
        """
        Get all points for a cell, optionally filtered by frame range.
        Returns list sorted by frame_index.
        """
        with self.get_connection() as conn:
            if frame_range:
                rows = conn.execute(
                    """SELECT * FROM points 
                       WHERE cell_id = ? AND frame_index >= ? AND frame_index <= ?
                       ORDER BY frame_index""",
                    (cell_id, frame_range[0], frame_range[1])
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM points WHERE cell_id = ? ORDER BY frame_index",
                    (cell_id,)
                ).fetchall()
            return [dict(row) for row in rows]
    
    def get_points_in_frame(self, frame_index: int) -> List[Dict[str, Any]]:
        """Get all points in a specific frame."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM points WHERE frame_index = ?",
                (frame_index,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_points_in_frame_range(self, start_frame: int, end_frame: int) -> List[Dict[str, Any]]:
        """Get all points within a frame range."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM points 
                   WHERE frame_index >= ? AND frame_index <= ?
                   ORDER BY frame_index, cell_id""",
                (start_frame, end_frame)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_cells_in_frame_range(self, start_frame: int, end_frame: int) -> List[int]:
        """Get unique cell IDs that have points in the given frame range."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT DISTINCT cell_id FROM points 
                   WHERE frame_index >= ? AND frame_index <= ?
                   ORDER BY cell_id""",
                (start_frame, end_frame)
            ).fetchall()
            return [row['cell_id'] for row in rows]
    
    # Event operations
    def add_event(self, event_type: str, frame_index: int, 
                  parent_cell_id: Optional[int] = None,
                  child_cell_id: Optional[int] = None,
                  metadata: Optional[Dict[str, Any]] = None):
        """Add a tracking event (division, merge, etc.)."""
        metadata_json = json.dumps(metadata) if metadata else None
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO events 
                   (event_type, parent_cell_id, child_cell_id, frame_index, metadata_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, parent_cell_id, child_cell_id, frame_index, metadata_json)
            )
            logger.info(f"Added event {event_type} at frame {frame_index}")
    
    # Run operations
    def start_run(self, batch_id: str, params: Dict[str, Any], 
                  frame_range_start: int, frame_range_end: int) -> int:
        """Start a new tracking run."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO runs 
                   (batch_id, params_json, frame_range_start, frame_range_end)
                   VALUES (?, ?, ?, ?)""",
                (batch_id, json.dumps(params), frame_range_start, frame_range_end)
            )
            run_id = cursor.lastrowid
            logger.info(f"Started run {run_id} for batch {batch_id}")
            return run_id
    
    def complete_run(self, run_id: int, xml_path: str, csv_paths: Dict[str, str]):
        """Mark a run as completed and store output paths."""
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE runs 
                   SET completed_at = CURRENT_TIMESTAMP, 
                       status = 'completed',
                       xml_path = ?,
                       csv_paths_json = ?
                   WHERE run_id = ?""",
                (xml_path, json.dumps(csv_paths), run_id)
            )
            logger.info(f"Completed run {run_id}")
    
    # Pipeline state operations
    def set_state(self, key: str, value: str):
        """Set a pipeline state value."""
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO pipeline_state (key, value, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (key, value)
            )
    
    def get_state(self, key: str) -> Optional[str]:
        """Get a pipeline state value."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM pipeline_state WHERE key = ?", (key,)
            ).fetchone()
            return row['value'] if row else None
    
    def get_finalized_frame(self) -> Optional[int]:
        """Get the last finalized frame index."""
        value = self.get_state('finalized_frame')
        return int(value) if value else None
    
    def set_finalized_frame(self, frame_index: int):
        """Set the last finalized frame index."""
        self.set_state('finalized_frame', str(frame_index))
        logger.info(f"Finalized frame updated to {frame_index}")
