"""
Configuration module for the cell tracking pipeline.
Centralizes all parameters and settings.
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class TrackerConfig:
    """Configuration for the incremental tracking pipeline."""
    
    # Fiji/ImageJ configuration
    fiji_path: str = os.environ.get("FIJI_PATH", "fiji")
    fiji_script: Path = Path(__file__).parent.parent / "fiji_scripts" / "run_trackmate_tail.groovy"
    
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
    db_path: Path = Path(__file__).parent.parent / "data" / "tracking.db"
    
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
