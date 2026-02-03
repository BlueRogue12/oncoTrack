"""
Frame ingestion module.
Discovers and processes image frames from batch directories.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class FrameIngester:
    """Handles frame discovery and metadata extraction."""
    
    SUPPORTED_EXTENSIONS = {'.png', '.tif', '.tiff', '.jpg', '.jpeg'}
    
    def __init__(self):
        pass
    
    @staticmethod
    def discover_frames(batch_dir: Path) -> List[Dict[str, Any]]:
        """
        Discover all valid image frames in a batch directory.
        
        Args:
            batch_dir: Path to directory containing frame images
            
        Returns:
            List of frame metadata dicts with keys: path, filename, frame_index, timestamp
        """
        if not batch_dir.exists():
            raise ValueError(f"Batch directory does not exist: {batch_dir}")
        
        if not batch_dir.is_dir():
            raise ValueError(f"Path is not a directory: {batch_dir}")
        
        frames = []
        
        # Find all image files
        for file_path in sorted(batch_dir.iterdir()):
            if file_path.suffix.lower() in FrameIngester.SUPPORTED_EXTENSIONS:
                # Skip Zone.Identifier files
                if file_path.name.endswith('.Zone.Identifier'):
                    continue
                    
                frame_info = FrameIngester._extract_frame_info(file_path)
                if frame_info:
                    frames.append(frame_info)
        
        # Sort by frame_index
        frames.sort(key=lambda f: f['frame_index'])
        
        logger.info(f"Discovered {len(frames)} frames in {batch_dir}")
        return frames
    
    @staticmethod
    def _extract_frame_info(file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract frame metadata from filename.
        
        Tries to extract frame index from filename patterns like:
        - cell_00001.png -> frame_index=1
        - frame_00042.png -> frame_index=42
        - img_0005.tif -> frame_index=5
        - frame_20240101_120000_000123.png -> extract from timestamp
        
        If no pattern matches, uses alphabetical order.
        """
        filename = file_path.name
        
        # Try to extract frame number from common patterns
        patterns = [
            r'cell_(\d+)',           # cell_00001.png
            r'frame_(\d+)',          # frame_00042.png
            r'img_(\d+)',            # img_0005.tif
            r'image_(\d+)',          # image_0010.png
            r'_(\d{5,})\.png$',      # _000123.png (5+ digits before extension)
            r'(\d{4,})',             # Any 4+ digit sequence
        ]
        
        frame_index = None
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                frame_index = int(match.group(1))
                break
        
        # Fallback: use file modification time as timestamp
        timestamp = file_path.stat().st_mtime
        
        if frame_index is None:
            # If no pattern matched, we'll assign indices later based on sort order
            logger.debug(f"Could not extract frame index from {filename}, will use sort order")
            frame_index = -1  # Placeholder
        
        return {
            'path': str(file_path.absolute()),
            'filename': filename,
            'frame_index': frame_index,
            'timestamp': timestamp
        }
    
    @staticmethod
    def assign_sequential_indices(frames: List[Dict[str, Any]], start_index: int = 0) -> List[Dict[str, Any]]:
        """
        Assign sequential frame indices starting from start_index.
        Useful when filenames don't contain frame numbers or when merging batches.
        
        Args:
            frames: List of frame metadata dicts
            start_index: Starting frame index
            
        Returns:
            Updated frames list with sequential indices
        """
        for i, frame in enumerate(frames):
            frame['frame_index'] = start_index + i
        
        logger.info(f"Assigned sequential indices {start_index} to {start_index + len(frames) - 1}")
        return frames
    
    @staticmethod
    def infer_batch_name(batch_dir: Path) -> str:
        """
        Infer a batch name from the directory path.
        
        Args:
            batch_dir: Path to batch directory
            
        Returns:
            Batch identifier string
        """
        # Use the directory name as batch ID
        return batch_dir.name
    
    @staticmethod
    def validate_frames(frames: List[Dict[str, Any]]) -> bool:
        """
        Validate that frames have unique indices and proper metadata.
        
        Args:
            frames: List of frame metadata dicts
            
        Returns:
            True if valid, raises ValueError otherwise
        """
        if not frames:
            raise ValueError("No frames to validate")
        
        # Check for unique frame indices
        indices = [f['frame_index'] for f in frames]
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate frame indices detected")
        
        # Check that all required fields are present
        required_fields = {'path', 'filename', 'frame_index', 'timestamp'}
        for frame in frames:
            missing = required_fields - set(frame.keys())
            if missing:
                raise ValueError(f"Frame missing required fields: {missing}")
        
        logger.info(f"Validated {len(frames)} frames")
        return True
    
    @staticmethod
    def get_frame_range(frames: List[Dict[str, Any]]) -> tuple[int, int]:
        """
        Get the frame index range (min, max) from a list of frames.
        
        Args:
            frames: List of frame metadata dicts
            
        Returns:
            Tuple of (min_frame_index, max_frame_index)
        """
        if not frames:
            raise ValueError("No frames provided")
        
        indices = [f['frame_index'] for f in frames]
        return min(indices), max(indices)


class BatchManager:
    """Manages batch processing and incremental updates."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.batches_dir = data_dir / "batches"
    
    def list_batches(self) -> List[str]:
        """List all available batch directories."""
        if not self.batches_dir.exists():
            return []
        
        batches = []
        for item in self.batches_dir.iterdir():
            if item.is_dir():
                batches.append(item.name)
        
        return sorted(batches)
    
    def get_batch_path(self, batch_name: str) -> Path:
        """Get the full path to a batch directory."""
        return self.batches_dir / batch_name
    
    def load_batch_frames(self, batch_name: str) -> List[Dict[str, Any]]:
        """
        Load and process frames from a batch.
        
        Args:
            batch_name: Name of the batch (directory name)
            
        Returns:
            List of frame metadata dicts
        """
        batch_path = self.get_batch_path(batch_name)
        frames = FrameIngester.discover_frames(batch_path)
        
        # If frames have placeholder indices, assign sequential ones
        if frames and frames[0]['frame_index'] == -1:
            frames = FrameIngester.assign_sequential_indices(frames, start_index=0)
        
        FrameIngester.validate_frames(frames)
        return frames
