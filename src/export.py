"""
Export module for master CSV and other output formats.
"""
import logging
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional

from .store import TrackingStore

logger = logging.getLogger(__name__)


class DataExporter:
    """Handles exporting tracking data to various formats."""
    
    def __init__(self, store: TrackingStore):
        self.store = store
    
    def export_master_csv(self, output_path: Path, cell_ids: Optional[List[int]] = None):
        """
        Export all tracking data to a master CSV file.
        
        CSV format:
        cell_id, frame_index, timestamp, x, y, quality, units
        
        Args:
            output_path: Path for output CSV file
            cell_ids: Optional list of cell IDs to export (None = all cells)
        """
        logger.info(f"Exporting master CSV to {output_path}")
        
        if cell_ids is None:
            cells = self.store.get_all_cells()
            cell_ids = [c['cell_id'] for c in cells]
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'cell_id', 'frame_index', 'timestamp', 'x', 'y', 
                'quality', 'units', 'first_frame', 'last_frame'
            ])
            
            total_rows = 0
            for cell_id in cell_ids:
                cell_info = self.store.get_cell(cell_id)
                if not cell_info:
                    continue
                
                points = self.store.get_cell_points(cell_id)
                
                for point in points:
                    # Get frame timestamp
                    frame_info = self.store.get_frame(point['frame_index'])
                    timestamp = frame_info['timestamp'] if frame_info else 0.0
                    
                    writer.writerow([
                        cell_id,
                        point['frame_index'],
                        timestamp,
                        point['x'],
                        point['y'],
                        point.get('quality', ''),
                        point.get('units', 'pixel'),
                        cell_info['first_frame'],
                        cell_info.get('last_frame', '')
                    ])
                    total_rows += 1
        
        logger.info(f"Exported {total_rows} points for {len(cell_ids)} cells to {output_path}")
    
    def export_cells_summary(self, output_path: Path):
        """
        Export a summary of all cells.
        
        CSV format:
        cell_id, first_frame, last_frame, num_points, duration_frames, displacement
        """
        logger.info(f"Exporting cells summary to {output_path}")
        
        cells = self.store.get_all_cells()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'cell_id', 'first_frame', 'last_frame', 'num_points', 
                'duration_frames', 'displacement_pixels'
            ])
            
            for cell in cells:
                cell_id = cell['cell_id']
                points = self.store.get_cell_points(cell_id)
                
                if not points:
                    continue
                
                num_points = len(points)
                first_frame = cell['first_frame']
                last_frame = cell.get('last_frame', points[-1]['frame_index'])
                duration = last_frame - first_frame + 1
                
                # Calculate displacement
                if num_points >= 2:
                    x0, y0 = points[0]['x'], points[0]['y']
                    xN, yN = points[-1]['x'], points[-1]['y']
                    displacement = ((xN - x0) ** 2 + (yN - y0) ** 2) ** 0.5
                else:
                    displacement = 0.0
                
                writer.writerow([
                    cell_id, first_frame, last_frame, num_points, duration, displacement
                ])
        
        logger.info(f"Exported summary for {len(cells)} cells")
    
    def export_events(self, output_path: Path):
        """
        Export all tracking events (divisions, merges, etc.).
        
        CSV format:
        event_id, event_type, parent_cell_id, child_cell_id, frame_index, metadata
        """
        logger.info(f"Exporting events to {output_path}")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Query all events from database
        with self.store.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY frame_index, event_id"
            ).fetchall()
            
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'event_id', 'event_type', 'parent_cell_id', 
                    'child_cell_id', 'frame_index', 'metadata'
                ])
                
                for row in rows:
                    writer.writerow([
                        row['event_id'],
                        row['event_type'],
                        row['parent_cell_id'],
                        row['child_cell_id'],
                        row['frame_index'],
                        row['metadata_json']
                    ])
        
        logger.info(f"Exported {len(rows)} events")
