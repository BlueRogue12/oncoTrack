"""
Main orchestration script for incremental cell tracking pipeline.

This script coordinates:
1. Frame ingestion from batch directories
2. TrackMate execution on tail windows
3. Track stitching with persistent cell IDs
4. Database persistence
5. Visualization and export
"""
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import TrackerConfig, get_default_config
from .store import TrackingStore
from .frame_ingest import FrameIngester, BatchManager
from .fiji_runner import FijiRunner
from .parse_trackmate_outputs import TrackMateParser
from .stitcher import TrackStitcher
from .export import DataExporter
from .visualize import TrackVisualizer

logger = logging.getLogger(__name__)


class IncrementalTracker:
    """Main orchestrator for incremental cell tracking."""
    
    def __init__(self, config: TrackerConfig):
        self.config = config
        self.store = TrackingStore(config.db_path)
        self.fiji_runner = FijiRunner(config)
        self.stitcher = TrackStitcher(
            self.store,
            min_overlap_points=config.min_overlap_points,
            max_distance_gate=config.max_distance_gate
        )
        self.exporter = DataExporter(self.store)
        self.visualizer = TrackVisualizer(self.store, config)
    
    def process_batch(self, batch_path: Path, batch_name: Optional[str] = None):
        """
        Process a new batch of frames incrementally.
        
        This is the main processing pipeline:
        1. Discover frames in batch
        2. Register frames in database
        3. Determine tail window for TrackMate
        4. Run TrackMate on tail window
        5. Parse TrackMate outputs
        6. Stitch tracks to persistent IDs
        7. Update finalized frame marker
        
        Args:
            batch_path: Path to batch directory containing frames
            batch_name: Optional batch identifier (defaults to directory name)
        """
        if batch_name is None:
            batch_name = batch_path.name
        
        logger.info(f"=" * 80)
        logger.info(f"Processing batch: {batch_name}")
        logger.info(f"Batch path: {batch_path}")
        logger.info(f"=" * 80)
        
        # Step 1: Discover frames
        logger.info("Step 1: Discovering frames")
        frames = FrameIngester.discover_frames(batch_path)
        
        if not frames:
            logger.error(f"No frames found in {batch_path}")
            return
        
        logger.info(f"Found {len(frames)} frames")
        
        # Step 2: Register frames in database
        logger.info("Step 2: Registering frames in database")
        for frame in frames:
            self.store.add_frame(
                frame_index=frame['frame_index'],
                timestamp=frame['timestamp'],
                source_path=frame['path']
            )
        
        frame_start, frame_end = FrameIngester.get_frame_range(frames)
        logger.info(f"Frame range: [{frame_start}, {frame_end}]")
        
        # Step 3: Determine tail window
        logger.info("Step 3: Determining tail window for TrackMate")
        
        finalized_frame = self.store.get_finalized_frame()
        if finalized_frame is None:
            # First batch - use all frames
            window_start = frame_start
            overlap_start = None
            logger.info("First batch - processing all frames")
        else:
            # Subsequent batch - use overlap window
            window_start = max(frame_start, finalized_frame - self.config.overlap_window + 1)
            overlap_start = finalized_frame + 1
            logger.info(
                f"Tail window: [{window_start}, {frame_end}], "
                f"overlap region: [{window_start}, {finalized_frame}], "
                f"new frames: [{overlap_start}, {frame_end}]"
            )
        
        # Step 4: Run TrackMate
        logger.info("Step 4: Running TrackMate on tail window")
        
        # Create output directory for this run
        run_output_dir = (
            self.config.db_path.parent / "trackmate_runs" / 
            f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{batch_name}"
        )
        run_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Start run record
        run_params = {
            'overlap_window': self.config.overlap_window,
            'detector': self.config.detector_type,
            'radius': self.config.radius,
            'threshold': self.config.threshold,
            'linking_max_distance': self.config.linking_max_distance,
        }
        
        run_id = self.store.start_run(
            batch_id=batch_name,
            params=run_params,
            frame_range_start=frame_start,
            frame_range_end=frame_end
        )
        
        try:
            trackmate_outputs = self.fiji_runner.run_trackmate_on_frames(
                frames_dir=batch_path,
                output_dir=run_output_dir
            )
            
            # Complete run record
            self.store.complete_run(
                run_id=run_id,
                xml_path=str(trackmate_outputs['xml']),
                csv_paths={k: str(v) for k, v in trackmate_outputs.items()}
            )
            
        except Exception as e:
            logger.error(f"TrackMate execution failed: {e}")
            raise
        
        # Step 5: Parse TrackMate outputs
        logger.info("Step 5: Parsing TrackMate outputs")
        tracks = TrackMateParser.parse_all(run_output_dir)
        logger.info(f"Parsed {len(tracks)} tracks from TrackMate")
        
        # Step 6: Stitch tracks
        logger.info("Step 6: Stitching tracks to persistent cell IDs")
        
        if finalized_frame is None:
            # First batch - all tracks are new cells
            logger.info("First batch - creating new cells for all tracks")
            
            track_to_cell = {}
            for track_id, track in tracks.items():
                first_frame = min(track.get_frames())
                cell_id = self.store.create_cell(first_frame=first_frame)
                track_to_cell[track_id] = cell_id
            
            # Add all points
            points_to_add = []
            for track_id, cell_id in track_to_cell.items():
                track = tracks[track_id]
                for spot in track.spots:
                    points_to_add.append({
                        'cell_id': cell_id,
                        'frame_index': spot.frame,
                        'x': spot.x,
                        'y': spot.y,
                        'quality': spot.quality,
                        'units': 'pixel'
                    })
            
            self.store.add_points(points_to_add)
            
            # Update last frames
            for cell_id in track_to_cell.values():
                points = self.store.get_cell_points(cell_id)
                if points:
                    last_frame = max(p['frame_index'] for p in points)
                    self.store.update_cell_last_frame(cell_id, last_frame)
            
            logger.info(f"Created {len(track_to_cell)} new cells, added {len(points_to_add)} points")
            
        else:
            # Subsequent batch - use stitching
            overlap_start_frame = window_start
            overlap_end_frame = finalized_frame
            new_frame_start = finalized_frame + 1
            
            result = self.stitcher.stitch_tracks(
                trackmate_tracks=tracks,
                overlap_frame_start=overlap_start_frame,
                overlap_frame_end=overlap_end_frame,
                new_frame_start=new_frame_start
            )
            
            logger.info(
                f"Stitching complete: {len(result.matched_cells)} total tracks, "
                f"{len(result.new_cells)} new cells, {result.total_points_added} points added"
            )
        
        # Step 7: Update finalized frame
        new_finalized_frame = frame_end - self.config.overlap_window
        if new_finalized_frame > (finalized_frame or -1):
            self.store.set_finalized_frame(new_finalized_frame)
            logger.info(f"Updated finalized frame to {new_finalized_frame}")
        
        logger.info(f"Batch {batch_name} processing complete")
    
    def export_data(self, output_dir: Path):
        """
        Export all tracking data.
        
        Args:
            output_dir: Directory for output files
        """
        logger.info(f"Exporting data to {output_dir}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export master CSV
        self.exporter.export_master_csv(output_dir / "master_tracks.csv")
        
        # Export cells summary
        self.exporter.export_cells_summary(output_dir / "cells_summary.csv")
        
        # Export events
        self.exporter.export_events(output_dir / "events.csv")
        
        logger.info("Export complete")
    
    def visualize(self, output_path: Path, background_image: Optional[Path] = None):
        """
        Visualize all tracks.
        
        Args:
            output_path: Path for output image
            background_image: Optional background image path
        """
        logger.info(f"Generating visualization")
        
        self.visualizer.render_all_tracks(
            output_path=output_path,
            background_image=background_image
        )
        
        logger.info(f"Visualization saved to {output_path}")


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Incremental cell tracking pipeline using Fiji/TrackMate"
    )
    
    parser.add_argument(
        '--batch',
        type=str,
        required=True,
        help='Path to batch directory containing frames'
    )
    
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export data after processing'
    )
    
    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Generate visualization after processing'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for exports and visualizations (default: output/)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        help='Override database path (default: data/tracking.db)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    logger.info("=" * 80)
    logger.info("Incremental Cell Tracking Pipeline")
    logger.info("=" * 80)
    
    # Load configuration
    config = get_default_config()
    if args.db_path:
        config.db_path = Path(args.db_path)
    
    # Create tracker
    tracker = IncrementalTracker(config)
    
    # Process batch
    batch_path = Path(args.batch)
    if not batch_path.exists():
        logger.error(f"Batch directory does not exist: {batch_path}")
        sys.exit(1)
    
    try:
        tracker.process_batch(batch_path)
        
        output_dir = Path(args.output_dir)
        
        # Export data if requested
        if args.export:
            tracker.export_data(output_dir / "exports")
        
        # Visualize if requested
        if args.visualize:
            vis_output = output_dir / "visualizations" / "tracks.png"
            tracker.visualize(vis_output)
        
        logger.info("=" * 80)
        logger.info("Pipeline completed successfully")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
