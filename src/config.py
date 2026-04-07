"""
Configuration module for the cell tracking pipeline.
Centralizes all parameters and settings.
"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _get_base_dir() -> Path:
    """Writable runtime root: exe dir when frozen, project root in dev."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_bundle_dir() -> Path:
    """Read-only bundled assets: _MEIPASS when frozen, project root in dev."""
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _default_fiji_path() -> str:
    """Auto-detect Fiji: env var → bundled Fiji/ folder → bare 'fiji'."""
    env_path = os.environ.get("FIJI_PATH", "")
    if env_path:
        return env_path
    bundled = _get_base_dir() / "Fiji" / "fiji-windows-x64.exe"
    if bundled.exists():
        return str(bundled)
    return "fiji"


@dataclass
class TrackerConfig:
    """Configuration for the incremental tracking pipeline."""

    # Fiji/ImageJ configuration
    fiji_path: str = field(default_factory=_default_fiji_path)
    fiji_script: Path = field(
        default_factory=lambda: _get_bundle_dir() / "fiji_scripts" / "run_trackmate_tail.groovy"
    )

    # Overlap window size (W frames)
    overlap_window: int = 3

    # Stitching parameters
    min_overlap_points: int = 2  # Minimum K overlapping points required
    max_distance_gate: float = 50.0  # Maximum distance in pixels per frame for matching

    # TrackMate detector parameters
    detector_type: str = "DOG_DETECTOR"  # Difference of Gaussian
    target_channel: int = 1
    radius: float = 5.0  # Cell radius in pixels
    threshold: float = 5.0  # Quality threshold
    do_subpixel: bool = True
    do_median_filter: bool = False

    # TrackMate LAP tracker parameters
    linking_max_distance: float = 50.0  # Max distance for frame-to-frame linking (increased for slow frame rate)
    gap_closing_max_distance: float = 50.0
    max_frame_gap: int = 2

    # Calibration
    pixel_size: float = 1.0  # microns per pixel (will be tuned)
    time_interval: float = 1.0  # seconds between frames
    spatial_units: str = "pixel"
    time_units: str = "sec"

    # Database
    db_path: Path = field(
        default_factory=lambda: _get_base_dir() / "data" / "tracking.db"
    )

    # Visualization
    vis_canvas_size: tuple[int, int] = (1024, 1024)
    vis_background_color: tuple[int, int, int] = (255, 255, 255)  # White
    vis_track_color: tuple[int, int, int] = (0, 128, 255)  # Orange-ish
    vis_point_radius: int = 4
    vis_line_thickness: int = 2

    # Logging
    log_level: str = "INFO"

    def __post_init__(self):
        """Ensure directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def get_default_config() -> TrackerConfig:
    """Get default configuration instance."""
    return TrackerConfig()
