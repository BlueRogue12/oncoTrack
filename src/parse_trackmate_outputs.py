"""
TrackMate output parser.
Parses CSV files exported by TrackMate into structured Python data.
"""
import logging
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Spot:
    """Represents a detected spot (cell) in a single frame."""
    spot_id: int
    frame: int
    x: float
    y: float
    quality: float
    radius: float
    
    def distance_to(self, other: 'Spot') -> float:
        """Calculate Euclidean distance to another spot."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass
class Track:
    """Represents a TrackMate track (sequence of linked spots)."""
    track_id: int
    spots: List[Spot]
    num_spots: int
    duration: float
    displacement: float
    
    def get_frames(self) -> List[int]:
        """Get list of frame indices where this track has spots."""
        return sorted([spot.frame for spot in self.spots])
    
    def get_spot_at_frame(self, frame: int) -> Optional[Spot]:
        """Get the spot in this track at a specific frame."""
        for spot in self.spots:
            if spot.frame == frame:
                return spot
        return None
    
    def get_spots_in_frame_range(self, start: int, end: int) -> List[Spot]:
        """Get spots within a frame range (inclusive)."""
        return [s for s in self.spots if start <= s.frame <= end]


class TrackMateParser:
    """Parser for TrackMate CSV outputs."""
    
    @staticmethod
    def parse_spots_csv(csv_path: Path) -> Dict[int, Spot]:
        """
        Parse spots.csv file.
        
        Args:
            csv_path: Path to spots.csv
            
        Returns:
            Dictionary mapping spot_id to Spot objects
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"Spots CSV not found: {csv_path}")
        
        spots = {}
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                spot = Spot(
                    spot_id=int(row['SPOT_ID']),
                    frame=int(row['FRAME']),
                    x=float(row['POSITION_X']),
                    y=float(row['POSITION_Y']),
                    quality=float(row['QUALITY']),
                    radius=float(row['RADIUS'])
                )
                spots[spot.spot_id] = spot
        
        logger.info(f"Parsed {len(spots)} spots from {csv_path}")
        return spots
    
    @staticmethod
    def parse_spots_in_tracks_csv(csv_path: Path) -> Dict[int, List[Spot]]:
        """
        Parse spots_in_tracks.csv file.
        
        Args:
            csv_path: Path to spots_in_tracks.csv
            
        Returns:
            Dictionary mapping track_id to list of Spot objects
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"Spots in tracks CSV not found: {csv_path}")
        
        tracks_spots = {}
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = int(row['TRACK_ID'])
                spot = Spot(
                    spot_id=int(row['SPOT_ID']),
                    frame=int(row['FRAME']),
                    x=float(row['POSITION_X']),
                    y=float(row['POSITION_Y']),
                    quality=float(row['QUALITY']),
                    radius=float(row['RADIUS'])
                )
                
                if track_id not in tracks_spots:
                    tracks_spots[track_id] = []
                tracks_spots[track_id].append(spot)
        
        # Sort spots by frame within each track
        for track_id in tracks_spots:
            tracks_spots[track_id].sort(key=lambda s: s.frame)
        
        logger.info(f"Parsed {len(tracks_spots)} tracks from {csv_path}")
        return tracks_spots
    
    @staticmethod
    def parse_tracks_csv(csv_path: Path) -> Dict[int, Dict[str, Any]]:
        """
        Parse tracks.csv file for track metadata.
        
        Args:
            csv_path: Path to tracks.csv
            
        Returns:
            Dictionary mapping track_id to track metadata
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"Tracks CSV not found: {csv_path}")
        
        tracks_meta = {}
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = int(row['TRACK_ID'])
                tracks_meta[track_id] = {
                    'num_spots': int(row['NUMBER_SPOTS']),
                    'duration': float(row['TRACK_DURATION']),
                    'displacement': float(row['TRACK_DISPLACEMENT']),
                    'track_start': float(row['TRACK_START']),
                    'track_stop': float(row['TRACK_STOP']),
                }
        
        logger.info(f"Parsed metadata for {len(tracks_meta)} tracks from {csv_path}")
        return tracks_meta
    
    @staticmethod
    def parse_all(output_dir: Path) -> Dict[int, Track]:
        """
        Parse all TrackMate outputs and build Track objects.
        
        Args:
            output_dir: Directory containing TrackMate CSV outputs
            
        Returns:
            Dictionary mapping track_id to Track objects
        """
        spots_in_tracks_path = output_dir / 'spots_in_tracks.csv'
        tracks_meta_path = output_dir / 'tracks.csv'
        
        # Parse spots organized by track
        tracks_spots = TrackMateParser.parse_spots_in_tracks_csv(spots_in_tracks_path)
        
        # Parse track metadata
        tracks_meta = TrackMateParser.parse_tracks_csv(tracks_meta_path)
        
        # Build Track objects
        tracks = {}
        for track_id, spots in tracks_spots.items():
            meta = tracks_meta.get(track_id, {})
            tracks[track_id] = Track(
                track_id=track_id,
                spots=spots,
                num_spots=meta.get('num_spots', len(spots)),
                duration=meta.get('duration', 0.0),
                displacement=meta.get('displacement', 0.0)
            )
        
        logger.info(f"Built {len(tracks)} Track objects")
        return tracks
    
    @staticmethod
    def get_frame_range(tracks: Dict[int, Track]) -> tuple[int, int]:
        """
        Get the frame range covered by all tracks.
        
        Args:
            tracks: Dictionary of Track objects
            
        Returns:
            Tuple of (min_frame, max_frame)
        """
        if not tracks:
            raise ValueError("No tracks provided")
        
        all_frames = []
        for track in tracks.values():
            all_frames.extend(track.get_frames())
        
        return min(all_frames), max(all_frames)
    
    @staticmethod
    def get_tracks_in_frame_range(
        tracks: Dict[int, Track],
        start_frame: int,
        end_frame: int
    ) -> Dict[int, Track]:
        """
        Filter tracks that have at least one spot in the given frame range.
        
        Args:
            tracks: Dictionary of Track objects
            start_frame: Start of frame range (inclusive)
            end_frame: End of frame range (inclusive)
            
        Returns:
            Filtered dictionary of Track objects
        """
        filtered = {}
        for track_id, track in tracks.items():
            frames = track.get_frames()
            if any(start_frame <= f <= end_frame for f in frames):
                filtered[track_id] = track
        
        logger.debug(f"Filtered to {len(filtered)} tracks in range [{start_frame}, {end_frame}]")
        return filtered
