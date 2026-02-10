"""
Visualization module for rendering cell tracks.
"""
import logging
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .store import TrackingStore
from .config import TrackerConfig

logger = logging.getLogger(__name__)


class TrackVisualizer:
    """Renders cell tracks on a canvas for visualization."""
    
    def __init__(self, store: TrackingStore, config: TrackerConfig):
        self.store = store
        self.config = config
    
    def render_all_tracks(
        self,
        output_path: Path,
        canvas_size: Optional[Tuple[int, int]] = None,
        background_image: Optional[Path] = None
    ):
        """
        Render all tracks on a white canvas or over a background image.
        
        Args:
            output_path: Path for output image file
            canvas_size: Optional canvas size (width, height), defaults to config
            background_image: Optional path to background image (e.g., latest frame)
        """
        logger.info("Rendering all tracks")
        
        # Determine canvas size
        if canvas_size is None:
            canvas_size = self.config.vis_canvas_size
        
        # Create canvas
        if background_image and background_image.exists():
            canvas = cv2.imread(str(background_image))
            if canvas is None:
                logger.warning(f"Failed to load background image: {background_image}")
                canvas = self._create_white_canvas(canvas_size)
            else:
                # Resize to canvas size if needed
                canvas = cv2.resize(canvas, canvas_size)
        else:
            canvas = self._create_white_canvas(canvas_size)
        
        # Get all cells
        cells = self.store.get_all_cells()
        logger.info(f"Rendering {len(cells)} cells")
        
        # Draw each cell track
        for cell in cells:
            cell_id = cell['cell_id']
            self._draw_cell_track(canvas, cell_id)
        
        # Save output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), canvas)
        logger.info(f"Saved visualization to {output_path}")
    
    def render_specific_cells(
        self,
        cell_ids: List[int],
        output_path: Path,
        canvas_size: Optional[Tuple[int, int]] = None,
        background_image: Optional[Path] = None
    ):
        """
        Render specific cell tracks.
        
        Args:
            cell_ids: List of cell IDs to render
            output_path: Path for output image file
            canvas_size: Optional canvas size (width, height)
            background_image: Optional background image path
        """
        logger.info(f"Rendering {len(cell_ids)} specific cells")
        
        if canvas_size is None:
            canvas_size = self.config.vis_canvas_size
        
        if background_image and background_image.exists():
            canvas = cv2.imread(str(background_image))
            if canvas is None:
                canvas = self._create_white_canvas(canvas_size)
            else:
                canvas = cv2.resize(canvas, canvas_size)
        else:
            canvas = self._create_white_canvas(canvas_size)
        
        for cell_id in cell_ids:
            self._draw_cell_track(canvas, cell_id)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), canvas)
        logger.info(f"Saved visualization to {output_path}")
    
    def _create_white_canvas(self, size: Tuple[int, int]) -> np.ndarray:
        """Create a white canvas of given size."""
        width, height = size
        canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
        return canvas
    
    def _draw_cell_track(self, canvas: np.ndarray, cell_id: int):
        """
        Draw a single cell track on the canvas.
        
        Args:
            canvas: OpenCV image array (modified in place)
            cell_id: Cell ID to draw
        """
        points = self.store.get_cell_points(cell_id)
        
        if len(points) < 1:
            return
        
        # Generate a unique color for this cell (based on cell_id)
        color = self._generate_color(cell_id)
        
        # Draw polyline connecting all points
        if len(points) >= 2:
            pts = np.array([
                [int(p['x']), int(p['y'])] for p in points
            ], dtype=np.int32)
            
            cv2.polylines(
                canvas, 
                [pts], 
                isClosed=False, 
                color=color, 
                thickness=self.config.vis_line_thickness
            )
        
        # Draw circles at each point
        for point in points:
            x, y = int(point['x']), int(point['y'])
            cv2.circle(
                canvas, 
                (x, y), 
                self.config.vis_point_radius, 
                color, 
                -1  # Filled circle
            )
        
        # Draw cell ID label at the last point
        if points:
            last_point = points[-1]
            x, y = int(last_point['x']), int(last_point['y'])
            
            # Draw text background for readability
            label = str(cell_id)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            
            (text_width, text_height), baseline = cv2.getTextSize(
                label, font, font_scale, thickness
            )
            
            # Draw white background rectangle
            cv2.rectangle(
                canvas,
                (x + 5, y - text_height - 5),
                (x + text_width + 10, y + 5),
                (255, 255, 255),
                -1
            )
            
            # Draw text
            cv2.putText(
                canvas,
                label,
                (x + 7, y - 2),
                font,
                font_scale,
                color,
                thickness
            )
    
    def _generate_color(self, cell_id: int) -> Tuple[int, int, int]:
        """
        Generate a unique color for a cell ID.
        
        Uses a simple hash-based color generation to ensure consistent colors.
        
        Args:
            cell_id: Cell ID
            
        Returns:
            BGR color tuple
        """
        # Use golden ratio for good color distribution
        golden_ratio = 0.618033988749895
        hue = (cell_id * golden_ratio) % 1.0
        
        # Convert HSV to RGB (OpenCV uses BGR)
        # Use high saturation and value for vibrant colors
        hsv = np.array([[[hue * 180, 200, 230]]], dtype=np.uint8)
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        color = tuple(map(int, bgr[0, 0]))
        return color
    
    def create_animation(
        self,
        output_path: Path,
        frame_rate: int = 10,
        canvas_size: Optional[Tuple[int, int]] = None
    ):
        """
        Create an animation showing track evolution over time.
        
        Args:
            output_path: Path for output video file
            frame_rate: Frames per second for video
            canvas_size: Optional canvas size
        """
        logger.info("Creating track animation (placeholder)")
        
        # This is a placeholder for future implementation
        # Would create a video showing tracks appearing frame by frame
        
        logger.warning("Animation export not yet implemented")
