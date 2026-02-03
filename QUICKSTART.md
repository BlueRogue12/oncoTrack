# OncoTrack Pipeline - Quick Start Guide

Get up and running with the incremental cell tracking pipeline in 5 minutes.

## Step 1: Install Dependencies

```bash
cd /home/phillip/code/oncoTrack

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt
```

## Step 2: Set Up Fiji

1. **Download Fiji**: https://fiji.sc/
2. **Install TrackMate**: Usually included with Fiji
3. **Set environment variable**:

   ```bash
   # Linux/Mac
   export FIJI_PATH=/path/to/fiji/ImageJ-linux64
   
   # Windows
   set FIJI_PATH=C:\path\to\fiji-win64.exe
   ```

   Add to `~/.bashrc` or `~/.zshrc` to make permanent.

## Step 3: Verify Installation

```bash
# Check Python environment
python --version  # Should be 3.11+
python -c "import cv2, numpy; print('OpenCV OK')"

# Check Fiji
$FIJI_PATH --version  # Should print Fiji/ImageJ version
```

## Step 4: Run Sample Processing

The repository includes sample frames in `data/batches/frames_1_3/`:

```bash
# Process first batch
python -m src.main \
    --batch data/batches/frames_1_3 \
    --visualize \
    --export \
    --log-level INFO

# Check outputs
ls -l data/tracking.db                    # SQLite database
ls -l output/visualizations/tracks.png    # Track visualization
ls -l output/exports/*.csv                # Exported CSVs
```

**Expected output**:
```
INFO - Processing batch: frames_1_3
INFO - Found 3 frames
INFO - Running TrackMate...
INFO - Parsed N tracks from TrackMate
INFO - Created N new cells
INFO - Visualization saved to output/visualizations/tracks.png
```

## Step 5: Process Incremental Updates

To simulate incremental processing, create additional batch folders:

```bash
# Create frames_1_6 batch (reuse frames 1-3 + add new ones)
mkdir -p data/batches/frames_1_6
cp data/batches/frames_1_3/*.png data/batches/frames_1_6/
# Add your new frames here (cell_00004.png, cell_00005.png, cell_00006.png)

# Process incrementally
python -m src.main \
    --batch data/batches/frames_1_6 \
    --visualize \
    --export
```

The pipeline will:
- Use frames 1-3 for overlap matching
- Add only frames 4-6 to the database
- Maintain consistent cell IDs across batches

## Understanding the Output

### Database (`data/tracking.db`)

Query with SQLite:

```bash
sqlite3 data/tracking.db

# View all cells
SELECT * FROM cells;

# View points for cell 1
SELECT * FROM points WHERE cell_id = 1 ORDER BY frame_index;

# View finalized frame
SELECT * FROM pipeline_state WHERE key = 'finalized_frame';
```

### Visualization (`output/visualizations/tracks.png`)

- Each cell gets a unique color
- Polylines show cell trajectory
- Circles mark detected positions
- Cell IDs labeled at final position

### Exports

1. **master_tracks.csv**: All cell positions with metadata
2. **cells_summary.csv**: Per-cell statistics (duration, displacement)
3. **events.csv**: Division/merge events (if detected)

## Troubleshooting

### "Fiji executable not found"

```bash
# Check if FIJI_PATH is set
echo $FIJI_PATH

# Test Fiji directly
$FIJI_PATH --help

# Fix: Set the correct path
export FIJI_PATH=/path/to/your/fiji/executable
```

### "No frames found"

Check that frames have supported extensions:

```bash
ls data/batches/frames_1_3/*.png
# Should show: cell_00001.png, cell_00002.png, cell_00003.png
```

### "TrackMate processing failed"

Check TrackMate parameters in `src/config.py`:
- Lower `threshold` if no spots detected
- Increase `radius` if cells are larger
- Check Fiji version supports TrackMate

### Run tests to verify setup

```bash
# Run unit tests
pytest tests/test_stitcher.py -v

# All tests should PASS
```

## Next Steps

1. **Capture your own frames**:
   ```bash
   python tools/frameCapture.py
   # Use GUI to select ROI and capture frames
   ```

2. **Tune parameters**: Edit `src/config.py`
   - Detector: `radius`, `threshold`
   - Tracker: `linking_max_distance`, `max_frame_gap`
   - Stitching: `overlap_window`, `max_distance_gate`

3. **Export data**: Access via SQLite or CSV exports

4. **Visualize**: Use the built-in visualizer or export to other tools

## Configuration Quick Reference

Edit `src/config.py`:

```python
# Overlap window size
overlap_window: int = 3

# TrackMate detector
radius: float = 5.0
threshold: float = 5.0

# TrackMate tracker
linking_max_distance: float = 15.0
max_frame_gap: int = 2

# Stitching
min_overlap_points: int = 2
max_distance_gate: float = 50.0
```

## Command Reference

```bash
# Basic run
python -m src.main --batch data/batches/frames_1_3

# With visualization
python -m src.main --batch data/batches/frames_1_3 --visualize

# With export
python -m src.main --batch data/batches/frames_1_3 --export

# Custom output directory
python -m src.main --batch data/batches/frames_1_3 --output-dir my_output

# Debug mode
python -m src.main --batch data/batches/frames_1_3 --log-level DEBUG

# Custom database
python -m src.main --batch data/batches/frames_1_3 --db-path custom.db
```

## Support

For detailed documentation, see `README_PIPELINE.md`.

For issues or questions, check:
1. Log output (--log-level DEBUG)
2. TrackMate outputs in `data/trackmate_runs/`
3. Database contents via SQLite
4. Unit test results: `pytest tests/ -v`
