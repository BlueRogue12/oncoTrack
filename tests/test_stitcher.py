"""
Unit tests for track stitching logic.
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from src.store import TrackingStore
from src.stitcher import TrackStitcher
from src.parse_trackmate_outputs import Track, Spot


class TestTrackStitcher(unittest.TestCase):
    """Test cases for TrackStitcher."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.store = TrackingStore(self.db_path)
        self.stitcher = TrackStitcher(
            self.store,
            min_overlap_points=2,
            max_distance_gate=50.0
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_first_batch_creates_new_cells(self):
        """Test that first batch creates new cells for all tracks."""
        # Create synthetic tracks
        track1 = Track(
            track_id=1,
            spots=[
                Spot(1, 0, 100.0, 100.0, 1.0, 5.0),
                Spot(2, 1, 105.0, 102.0, 1.0, 5.0),
                Spot(3, 2, 110.0, 105.0, 1.0, 5.0),
            ],
            num_spots=3,
            duration=2.0,
            displacement=10.0
        )
        
        track2 = Track(
            track_id=2,
            spots=[
                Spot(4, 0, 200.0, 200.0, 1.0, 5.0),
                Spot(5, 1, 202.0, 205.0, 1.0, 5.0),
                Spot(6, 2, 205.0, 210.0, 1.0, 5.0),
            ],
            num_spots=3,
            duration=2.0,
            displacement=10.0
        )
        
        tracks = {1: track1, 2: track2}
        
        # Register frames
        for i in range(3):
            self.store.add_frame(i, float(i), f"frame_{i}.png")
        
        # Stitch (no existing data, so all are new)
        result = self.stitcher.stitch_tracks(
            trackmate_tracks=tracks,
            overlap_frame_start=0,
            overlap_frame_end=0,
            new_frame_start=0
        )
        
        # Verify results
        self.assertEqual(result.total_tracks, 2)
        self.assertEqual(len(result.new_cells), 2)
        self.assertEqual(result.total_points_added, 6)
        
        # Verify cells were created
        cells = self.store.get_all_cells()
        self.assertEqual(len(cells), 2)
    
    def test_overlap_matching_exact(self):
        """Test that tracks with exact overlap are matched correctly."""
        # Add existing cell with points in frames 0-2
        cell_id = self.store.create_cell(first_frame=0)
        
        existing_points = [
            {'cell_id': cell_id, 'frame_index': 0, 'x': 100.0, 'y': 100.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 1, 'x': 105.0, 'y': 102.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 2, 'x': 110.0, 'y': 105.0, 'quality': 1.0, 'units': 'pixel'},
        ]
        
        for i in range(5):
            self.store.add_frame(i, float(i), f"frame_{i}.png")
        
        self.store.add_points(existing_points)
        self.store.set_finalized_frame(2)
        
        # Create new track that overlaps frames 1-2 and extends to 3-4
        track1 = Track(
            track_id=1,
            spots=[
                Spot(1, 1, 105.0, 102.0, 1.0, 5.0),  # Exact match
                Spot(2, 2, 110.0, 105.0, 1.0, 5.0),  # Exact match
                Spot(3, 3, 115.0, 108.0, 1.0, 5.0),  # New
                Spot(4, 4, 120.0, 112.0, 1.0, 5.0),  # New
            ],
            num_spots=4,
            duration=3.0,
            displacement=15.0
        )
        
        tracks = {1: track1}
        
        # Stitch with overlap in frames 1-2
        result = self.stitcher.stitch_tracks(
            trackmate_tracks=tracks,
            overlap_frame_start=1,
            overlap_frame_end=2,
            new_frame_start=3
        )
        
        # Should match to existing cell
        self.assertIn(1, result.matched_cells)
        self.assertEqual(result.matched_cells[1], cell_id)
        self.assertEqual(len(result.new_cells), 0)
        self.assertEqual(result.total_points_added, 2)  # Only frames 3-4
        
        # Verify points were added
        all_points = self.store.get_cell_points(cell_id)
        self.assertEqual(len(all_points), 5)  # 3 original + 2 new
    
    def test_overlap_matching_with_noise(self):
        """Test matching with slight positional noise."""
        # Add existing cell
        cell_id = self.store.create_cell(first_frame=0)
        
        existing_points = [
            {'cell_id': cell_id, 'frame_index': 0, 'x': 100.0, 'y': 100.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 1, 'x': 105.0, 'y': 102.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 2, 'x': 110.0, 'y': 105.0, 'quality': 1.0, 'units': 'pixel'},
        ]
        
        for i in range(4):
            self.store.add_frame(i, float(i), f"frame_{i}.png")
        
        self.store.add_points(existing_points)
        self.store.set_finalized_frame(2)
        
        # Create track with slight noise (within tolerance)
        track1 = Track(
            track_id=1,
            spots=[
                Spot(1, 1, 106.0, 103.0, 1.0, 5.0),  # +1 pixel offset
                Spot(2, 2, 111.0, 106.0, 1.0, 5.0),  # +1 pixel offset
                Spot(3, 3, 116.0, 109.0, 1.0, 5.0),  # New
            ],
            num_spots=3,
            duration=2.0,
            displacement=10.0
        )
        
        tracks = {1: track1}
        
        # Should still match (within distance gate)
        result = self.stitcher.stitch_tracks(
            trackmate_tracks=tracks,
            overlap_frame_start=1,
            overlap_frame_end=2,
            new_frame_start=3
        )
        
        self.assertEqual(len(result.new_cells), 0)
        self.assertIn(1, result.matched_cells)
    
    def test_no_match_creates_new_cell(self):
        """Test that tracks without good matches create new cells."""
        # Add existing cell
        cell_id = self.store.create_cell(first_frame=0)
        
        existing_points = [
            {'cell_id': cell_id, 'frame_index': 0, 'x': 100.0, 'y': 100.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 1, 'x': 105.0, 'y': 102.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 2, 'x': 110.0, 'y': 105.0, 'quality': 1.0, 'units': 'pixel'},
        ]
        
        for i in range(4):
            self.store.add_frame(i, float(i), f"frame_{i}.png")
        
        self.store.add_points(existing_points)
        self.store.set_finalized_frame(2)
        
        # Create track far away (should not match)
        track1 = Track(
            track_id=1,
            spots=[
                Spot(1, 1, 500.0, 500.0, 1.0, 5.0),  # Far away
                Spot(2, 2, 505.0, 502.0, 1.0, 5.0),
                Spot(3, 3, 510.0, 505.0, 1.0, 5.0),
            ],
            num_spots=3,
            duration=2.0,
            displacement=10.0
        )
        
        tracks = {1: track1}
        
        result = self.stitcher.stitch_tracks(
            trackmate_tracks=tracks,
            overlap_frame_start=1,
            overlap_frame_end=2,
            new_frame_start=3
        )
        
        # Should create new cell
        self.assertEqual(len(result.new_cells), 1)
        self.assertIn(1, result.new_cells)
        
        # Verify two cells exist
        cells = self.store.get_all_cells()
        self.assertEqual(len(cells), 2)
    
    def test_insufficient_overlap_creates_new_cell(self):
        """Test that tracks with insufficient overlap points create new cells."""
        # Add existing cell
        cell_id = self.store.create_cell(first_frame=0)
        
        existing_points = [
            {'cell_id': cell_id, 'frame_index': 0, 'x': 100.0, 'y': 100.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 1, 'x': 105.0, 'y': 102.0, 'quality': 1.0, 'units': 'pixel'},
            {'cell_id': cell_id, 'frame_index': 2, 'x': 110.0, 'y': 105.0, 'quality': 1.0, 'units': 'pixel'},
        ]
        
        for i in range(4):
            self.store.add_frame(i, float(i), f"frame_{i}.png")
        
        self.store.add_points(existing_points)
        self.store.set_finalized_frame(2)
        
        # Create track with only 1 overlap point (< min_overlap_points)
        track1 = Track(
            track_id=1,
            spots=[
                Spot(1, 2, 110.0, 105.0, 1.0, 5.0),  # Only 1 overlap
                Spot(2, 3, 115.0, 108.0, 1.0, 5.0),
            ],
            num_spots=2,
            duration=1.0,
            displacement=5.0
        )
        
        tracks = {1: track1}
        
        result = self.stitcher.stitch_tracks(
            trackmate_tracks=tracks,
            overlap_frame_start=1,
            overlap_frame_end=2,
            new_frame_start=3
        )
        
        # Should create new cell (insufficient overlap)
        self.assertEqual(len(result.new_cells), 1)


if __name__ == '__main__':
    unittest.main()
