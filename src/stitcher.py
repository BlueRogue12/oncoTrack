"""
Track stitching module.
Implements overlap-based matching to maintain persistent cell IDs across TrackMate runs.
"""
import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from .parse_trackmate_outputs import Track, Spot
from .store import TrackingStore

logger = logging.getLogger(__name__)


@dataclass
class StitchingResult:
    """Result of a stitching operation."""
    matched_cells: Dict[int, int]  # trackmate_track_id -> cell_id
    new_cells: List[int]  # trackmate_track_ids that became new cells
    division_events: List[Tuple[int, int, int]]  # (parent_cell_id, child1_cell_id, frame)
    total_tracks: int
    total_points_added: int


class TrackStitcher:
    """Handles stitching of TrackMate tracks to persistent cell IDs."""
    
    def __init__(
        self,
        store: TrackingStore,
        min_overlap_points: int = 2,
        max_distance_gate: float = 50.0
    ):
        """
        Initialize track stitcher.
        
        Args:
            store: TrackingStore instance for database access
            min_overlap_points: Minimum number of overlapping points required for matching
            max_distance_gate: Maximum mean distance per frame for matching (pixels)
        """
        self.store = store
        self.min_overlap_points = min_overlap_points
        self.max_distance_gate = max_distance_gate
    
    def stitch_tracks(
        self,
        trackmate_tracks: Dict[int, Track],
        overlap_frame_start: int,
        overlap_frame_end: int,
        new_frame_start: int
    ) -> StitchingResult:
        """
        Stitch TrackMate tracks to existing persistent cell IDs.
        
        This is the core stitching algorithm that:
        1. Identifies overlap region between existing data and new tracks
        2. Matches tracks to existing cells using cost matrix
        3. Creates new cells for unmatched tracks
        4. Detects division events
        5. Adds only new points (beyond overlap) to database
        
        Args:
            trackmate_tracks: Dictionary of TrackMate Track objects
            overlap_frame_start: Start of overlap window
            overlap_frame_end: End of overlap window
            new_frame_start: First frame with new data (beyond last finalized)
            
        Returns:
            StitchingResult with matching details
        """
        logger.info(
            f"Stitching {len(trackmate_tracks)} tracks with overlap "
            f"[{overlap_frame_start}, {overlap_frame_end}], new data from {new_frame_start}"
        )
        
        # Get existing cells that have points in overlap region
        existing_cells = self._get_existing_cells_in_overlap(
            overlap_frame_start, overlap_frame_end
        )
        
        logger.info(f"Found {len(existing_cells)} existing cells in overlap region")
        
        # Build cost matrix for matching
        matches = self._match_tracks_to_cells(
            trackmate_tracks, existing_cells, overlap_frame_start, overlap_frame_end
        )
        
        # Identify unmatched tracks (new cells)
        matched_track_ids = set(matches.values())
        all_track_ids = set(trackmate_tracks.keys())
        new_track_ids = all_track_ids - matched_track_ids
        
        logger.info(f"Matched {len(matches)} tracks, {len(new_track_ids)} new tracks")
        
        # Create mapping: trackmate_track_id -> cell_id
        track_to_cell = {}
        
        # Add matched tracks
        for cell_id, track_id in matches.items():
            track_to_cell[track_id] = cell_id
        
        # Create new cells for unmatched tracks
        new_cell_ids = []
        for track_id in new_track_ids:
            track = trackmate_tracks[track_id]
            first_frame = min(track.get_frames())
            cell_id = self.store.create_cell(first_frame=first_frame)
            track_to_cell[track_id] = cell_id
            new_cell_ids.append(track_id)
        
        # Detect division events
        division_events = self._detect_divisions(
            trackmate_tracks, track_to_cell, existing_cells, 
            overlap_frame_start, overlap_frame_end
        )
        
        # Add points for new frames only
        total_points = self._add_new_points(
            trackmate_tracks, track_to_cell, new_frame_start
        )
        
        result = StitchingResult(
            matched_cells=track_to_cell,
            new_cells=new_cell_ids,
            division_events=division_events,
            total_tracks=len(trackmate_tracks),
            total_points_added=total_points
        )
        
        logger.info(
            f"Stitching complete: {len(matches)} matched, {len(new_cell_ids)} new, "
            f"{total_points} points added, {len(division_events)} divisions"
        )
        
        return result
    
    def _get_existing_cells_in_overlap(
        self, start_frame: int, end_frame: int
    ) -> Dict[int, List[Dict]]:
        """
        Get existing cells with their points in the overlap region.
        
        Returns:
            Dictionary mapping cell_id to list of point dicts
        """
        cell_ids = self.store.get_cells_in_frame_range(start_frame, end_frame)
        
        cells_data = {}
        for cell_id in cell_ids:
            points = self.store.get_cell_points(cell_id, (start_frame, end_frame))
            if len(points) >= self.min_overlap_points:
                cells_data[cell_id] = points
        
        return cells_data
    
    def _match_tracks_to_cells(
        self,
        tracks: Dict[int, Track],
        existing_cells: Dict[int, List[Dict]],
        start_frame: int,
        end_frame: int
    ) -> Dict[int, int]:
        """
        Match TrackMate tracks to existing cells using overlap comparison.
        
        Uses Hungarian algorithm (greedy approximation) with cost based on
        mean squared distance in overlap region.
        
        Args:
            tracks: TrackMate tracks
            existing_cells: Existing cells with points in overlap
            start_frame: Overlap start
            end_frame: Overlap end
            
        Returns:
            Dictionary mapping cell_id -> trackmate_track_id (best match)
        """
        if not existing_cells or not tracks:
            return {}
        
        # Build cost matrix: [cell][track] = cost
        cell_ids = list(existing_cells.keys())
        track_ids = list(tracks.keys())
        
        # Cost matrix: rows=cells, cols=tracks
        cost_matrix = np.full((len(cell_ids), len(track_ids)), np.inf)
        
        for i, cell_id in enumerate(cell_ids):
            cell_points = existing_cells[cell_id]
            
            # Build dict of frame -> point for this cell
            cell_frame_map = {p['frame_index']: p for p in cell_points}
            
            for j, track_id in enumerate(track_ids):
                track = tracks[track_id]
                
                # Get track spots in overlap region
                track_spots = track.get_spots_in_frame_range(start_frame, end_frame)
                
                if len(track_spots) < self.min_overlap_points:
                    continue
                
                # Calculate overlap cost
                cost = self._calculate_overlap_cost(
                    cell_frame_map, track_spots
                )
                
                if cost is not None and cost < self.max_distance_gate:
                    cost_matrix[i, j] = cost
        
        # Greedy matching: for each cell, find best track
        matches = {}  # cell_id -> track_id
        matched_tracks = set()
        
        # Sort cells by minimum cost
        cell_costs = [(i, np.min(cost_matrix[i, :])) for i in range(len(cell_ids))]
        cell_costs.sort(key=lambda x: x[1])
        
        for i, min_cost in cell_costs:
            if min_cost == np.inf:
                continue
            
            # Find best unmatched track for this cell
            for j in range(len(track_ids)):
                if j in matched_tracks:
                    continue
                if cost_matrix[i, j] < self.max_distance_gate:
                    matches[cell_ids[i]] = track_ids[j]
                    matched_tracks.add(j)
                    logger.debug(
                        f"Matched cell {cell_ids[i]} to track {track_ids[j]} "
                        f"with cost {cost_matrix[i, j]:.2f}"
                    )
                    break
        
        return matches
    
    def _calculate_overlap_cost(
        self,
        cell_frame_map: Dict[int, Dict],
        track_spots: List[Spot]
    ) -> Optional[float]:
        """
        Calculate cost (mean squared distance) between cell and track in overlap.
        
        Args:
            cell_frame_map: Dictionary mapping frame -> cell point
            track_spots: List of track spots in overlap region
            
        Returns:
            Mean squared distance, or None if insufficient overlap
        """
        distances = []
        
        for spot in track_spots:
            if spot.frame in cell_frame_map:
                cell_point = cell_frame_map[spot.frame]
                dx = spot.x - cell_point['x']
                dy = spot.y - cell_point['y']
                dist = (dx * dx + dy * dy) ** 0.5
                distances.append(dist)
        
        if len(distances) < self.min_overlap_points:
            return None
        
        # Return mean distance
        return float(np.mean(distances))
    
    def _detect_divisions(
        self,
        tracks: Dict[int, Track],
        track_to_cell: Dict[int, int],
        existing_cells: Dict[int, List[Dict]],
        start_frame: int,
        end_frame: int
    ) -> List[Tuple[int, int, int]]:
        """
        Detect division events where one cell splits into two.
        
        Simple heuristic: If two tracks are very close at their start frame
        and both match regions near a single existing cell, it's a division.
        
        Args:
            tracks: TrackMate tracks
            track_to_cell: Mapping from track_id to cell_id
            existing_cells: Existing cells data
            start_frame: Overlap start
            end_frame: Overlap end
            
        Returns:
            List of (parent_cell_id, child_cell_id, frame_index) tuples
        """
        # Simplified division detection
        # In production, this would be more sophisticated
        divisions = []
        
        # For now, just log potential divisions for manual inspection
        # Real implementation would check for tracks that:
        # 1. Start at similar frame/position
        # 2. Have matching parent in previous frames
        
        logger.debug("Division detection: simplified placeholder")
        
        return divisions
    
    def _add_new_points(
        self,
        tracks: Dict[int, Track],
        track_to_cell: Dict[int, int],
        new_frame_start: int
    ) -> int:
        """
        Add points from tracks for frames >= new_frame_start to database.
        
        Args:
            tracks: TrackMate tracks
            track_to_cell: Mapping from track_id to cell_id
            new_frame_start: First frame with new data
            
        Returns:
            Number of points added
        """
        points_to_add = []
        
        for track_id, cell_id in track_to_cell.items():
            track = tracks[track_id]
            
            for spot in track.spots:
                if spot.frame >= new_frame_start:
                    points_to_add.append({
                        'cell_id': cell_id,
                        'frame_index': spot.frame,
                        'x': spot.x,
                        'y': spot.y,
                        'quality': spot.quality,
                        'units': 'pixel'
                    })
        
        if points_to_add:
            self.store.add_points(points_to_add)
            
            # Update last_frame for each cell
            cell_last_frames = {}
            for point in points_to_add:
                cell_id = point['cell_id']
                frame = point['frame_index']
                if cell_id not in cell_last_frames or frame > cell_last_frames[cell_id]:
                    cell_last_frames[cell_id] = frame
            
            for cell_id, last_frame in cell_last_frames.items():
                self.store.update_cell_last_frame(cell_id, last_frame)
        
        return len(points_to_add)
