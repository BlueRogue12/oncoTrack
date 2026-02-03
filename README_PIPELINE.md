# OncoTrack: Incremental Cell Tracking Pipeline

A hybrid cell-tracking system that uses Fiji/TrackMate headless for detection and tracking, with Python orchestration for incremental updates, persistent cell ID stitching, SQLite persistence, and visualization.

## Overview

This pipeline processes microscope frames incrementally:
- **Producer**: `tools/frameCapture.py` (Qt GUI for screen capture)
- **Consumer**: This tracking pipeline (processes saved frames)

### Key Features

- **Incremental Processing**: Process frames in batches without recomputing everything
- **Persistent Cell IDs**: Maintain stable cell identities across TrackMate runs using overlap-based stitching
- **Hybrid Architecture**: Fiji/TrackMate for robust detection + Python for orchestration
- **SQLite Persistence**: All tracking data stored in a single `.db` file
- **Deterministic**: Same inputs + settings = same outputs
- **Visualization**: Draw tracks on canvas for validation

## Architecture

```
┌─────────────────┐
│ Frame Producer  │  (tools/frameCapture.py - DO NOT MODIFY)
│  (Qt GUI)       │
└────────┬────────┘
         │ Saves PNG frames
         ↓
┌─────────────────────────────────────────────────────────┐
│              TRACKING PIPELINE                          │
│                                                         │
│  1. Frame Ingestion  → Discover & register frames      │
│  2. Fiji/TrackMate   → Detection + LAP tracking        │
│  3. Parse Outputs    → CSV → Python Track objects      │
│  4. Stitching        → Match tracks to persistent IDs  │
│  5. SQLite Storage   → Append new data                 │
│  6. Visualization    → Render tracks on canvas         │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
oncoTrack/
├── tools/                    # EXTERNAL - DO NOT MODIFY
│   └── frameCapture.py       # Frame capture UI (finished)
├── data/
│   ├── batches/              # Input frame batches
│   │   ├── frames_1_3/       # First batch (frames 1-3)
│   │   ├── frames_1_6/       # Second batch (frames 1-6)
│   │   └── frames_1_9/       # Third batch (frames 1-9)
│   ├── tracking.db           # SQLite database (generated)
│   └── trackmate_runs/       # TrackMate outputs (generated)
├── fiji_scripts/
│   └── run_trackmate_tail.groovy  # Headless TrackMate script
├── src/
│   ├── __init__.py
│   ├── config.py             # Configuration and parameters
│   ├── store.py              # SQLite persistence layer
│   ├── frame_ingest.py       # Frame discovery and metadata
│   ├── fiji_runner.py        # Fiji headless wrapper
│   ├── parse_trackmate_outputs.py  # CSV parsing
│   ├── stitcher.py           # Overlap-based track stitching
│   ├── export.py             # Master CSV export
│   ├── visualize.py          # OpenCV visualization
│   └── main.py               # Main orchestration
├── tests/
│   ├── __init__.py
│   └── test_stitcher.py      # Unit tests for stitching logic
├── output/                   # Exports and visualizations
├── requirements.txt
└── README_PIPELINE.md        # This file
```

## Installation

### Prerequisites

1. **Python 3.11+**
   ```bash
   python --version
   ```

2. **Fiji/ImageJ with TrackMate**
   - Download: https://fiji.sc/
   - Ensure TrackMate plugin is installed (usually comes with Fiji)
   - Set environment variable:
     ```bash
     export FIJI_PATH=/path/to/Fiji.app/Contents/MacOS/ImageJ-macosx
     # Or on Linux:
     export FIJI_PATH=/path/to/fiji/ImageJ-linux64
     # Or on Windows:
     set FIJI_PATH=C:\path\to\fiji-win64.exe
     ```

### Install Python Dependencies

```bash
cd oncoTrack
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Basic Workflow

1. **Capture frames** (using existing tool - DO NOT MODIFY):
   ```bash
   python tools/frameCapture.py
   ```
   Frames are saved to `~/Documents/OncoTrackSnaps/`

2. **Organize frames into batches**:
   ```bash
   # Copy frames to batch directories
   cp ~/Documents/OncoTrackSnaps/frame_*.png data/batches/frames_1_3/
   ```

3. **Run tracking pipeline**:
   ```bash
   # Process first batch
   python -m src.main --batch data/batches/frames_1_3 --visualize --export

   # Process subsequent batches (incremental)
   python -m src.main --batch data/batches/frames_1_6 --visualize --export
   python -m src.main --batch data/batches/frames_1_9 --visualize --export
   ```

### Command-Line Options

```bash
python -m src.main --help

Options:
  --batch PATH          Path to batch directory (required)
  --export              Export master CSV after processing
  --visualize           Generate track visualization
  --output-dir PATH     Output directory (default: output/)
  --log-level LEVEL     Logging level: DEBUG|INFO|WARNING|ERROR
  --db-path PATH        Override database path
```

### Example: Complete Run

```bash
# Process with visualization and export
python -m src.main \
    --batch data/batches/frames_1_3 \
    --visualize \
    --export \
    --output-dir output \
    --log-level INFO
```

## How It Works

### Incremental Processing Model

The pipeline maintains a **finalized frame** marker:
- Frames ≤ finalized_frame are **immutable** (never reprocessed)
- The last W frames form an **overlap window** (mutable, re-tracked each update)
- Only new data beyond finalized_frame is appended to the database

```
Batch 1: Frames [0, 1, 2, 3]
  → All frames are new
  → Finalized frame = 3 - W = 1 (with W=3)

Batch 2: Frames [0, 1, 2, 3, 4, 5]
  → Overlap: [1, 2, 3] (used for matching)
  → New: [4, 5] (added to database)
  → Finalized frame = 5 - 3 = 2
```

### Track Stitching Algorithm

Matches TrackMate tracks to persistent cell IDs using overlap region:

1. **Extract overlap**: Get existing cell positions in frames [finalized_frame - W + 1, finalized_frame]
2. **Build cost matrix**: For each (cell, track) pair, compute mean distance in overlap
3. **Greedy matching**: Assign tracks to cells with minimum cost (< max_distance_gate)
4. **Create new cells**: Unmatched tracks become new cells
5. **Append points**: Add only data for frames > finalized_frame

**Parameters** (in `src/config.py`):
- `overlap_window = 3`: Number of frames to re-track
- `min_overlap_points = 2`: Minimum overlapping detections required
- `max_distance_gate = 50.0`: Maximum mean distance (pixels) for matching

### SQLite Schema

**Tables**:
- `frames`: Frame metadata (index, timestamp, source path)
- `cells`: Cell entities (cell_id, first_frame, last_frame)
- `points`: Cell positions (cell_id, frame_index, x, y, quality)
- `events`: Division/merge events
- `runs`: TrackMate run metadata (params, XML paths)
- `pipeline_state`: Finalized frame marker

### TrackMate Configuration

**Detector**: Difference of Gaussian (DoG)
- `radius = 5.0` pixels
- `threshold = 5.0` quality threshold
- `do_subpixel = true`

**Tracker**: LAP (Linear Assignment Problem)
- `linking_max_distance = 15.0` pixels
- `gap_closing_max_distance = 15.0` pixels
- `max_frame_gap = 2` frames

Tune these in `src/config.py`.

## Testing

Run unit tests:

```bash
# All tests
pytest tests/

# With coverage
pytest --cov=src tests/

# Specific test
pytest tests/test_stitcher.py -v
```

Tests cover:
- First batch processing (all new cells)
- Overlap matching with exact positions
- Overlap matching with positional noise
- New cell creation for unmatched tracks
- Insufficient overlap handling

## Output Files

### After Processing

- `data/tracking.db`: SQLite database with all tracking data
- `data/trackmate_runs/run_*/`: TrackMate outputs (XML + CSV)

### With `--export`

- `output/exports/master_tracks.csv`: All cell positions
- `output/exports/cells_summary.csv`: Per-cell statistics
- `output/exports/events.csv`: Division/merge events

### With `--visualize`

- `output/visualizations/tracks.png`: Rendered tracks on white canvas

## Configuration

Edit `src/config.py` to change:
- TrackMate detector/tracker parameters
- Overlap window size
- Stitching thresholds
- Visualization colors
- Database path

## Troubleshooting

### Fiji Not Found

```
RuntimeError: Fiji executable not found: fiji
```

**Solution**: Set `FIJI_PATH` environment variable:
```bash
export FIJI_PATH=/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx
```

### No Frames Detected

```
ERROR: No frames found in data/batches/frames_1_3
```

**Solution**: Ensure frames are in the batch directory with supported extensions (.png, .tif, .jpg)

### TrackMate Fails

Check TrackMate output in logs. Common issues:
- Image stack too small (need ≥2 frames)
- No spots detected (adjust detector threshold)
- Fiji plugin missing (reinstall TrackMate)

### Stitching Produces Too Many New Cells

**Solution**: Increase `max_distance_gate` or decrease `min_overlap_points` in config

## Future Enhancements

- [ ] Division detection (currently placeholder)
- [ ] Track merging detection
- [ ] Quality filtering (remove low-quality tracks)
- [ ] Export animation (video of tracks over time)
- [ ] Web UI for visualization
- [ ] Real-time processing mode
- [ ] Multi-channel support
- [ ] 3D tracking (z-stacks)

## CRITICAL: Do Not Modify

**DO NOT** modify, refactor, move, rename, or rewrite:
- `tools/frameCapture.py`
- Any files in `tools/` directory

These are external, finished utilities. The pipeline only consumes their output.

## License

Internal research tool for OncoTrack project.

## Contact

For questions or issues, contact the development team.
