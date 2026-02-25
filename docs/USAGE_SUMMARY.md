# OncoTrack Pipeline - Usage Summary

Quick reference for running the pipeline with team-friendly configuration.

## 🎯 Your Current Setup

Your `.env` file is configured with:
```bash
FIJI_PATH=/home/username/Fiji/fiji-linux-x64
FRAMES_PATH=vid1_frames
```

## 🚀 Quick Commands

### Run with .env defaults
```bash
./run_test.sh --visualize --export
```

### Override frame path
```bash
./run_test.sh --batch /path/to/other/frames --visualize
```

### Clean and start fresh
```bash
./run_test.sh --clean --visualize --export
```

### Run with specific batch from data folder
```bash
./run_test.sh --batch data/batches/frames_1_6 --visualize
```

---

## 📝 Configuration Options

Edit `.env` to change defaults:

```bash
# Your Fiji installation
FIJI_PATH=/home/username/Fiji/fiji-linux-x64

# Default frames directory (can be relative or absolute)
FRAMES_PATH=vid1_frames

# Optional overrides
# DB_PATH=data/tracking.db
# OUTPUT_DIR=output
# LOG_LEVEL=INFO
```

---

## 👥 For Your Team

Each team member should:

1. **Clone the repo**
2. **Run setup**: `./setup_env.sh`
3. **Edit `.env`** with their own paths:
   - `FIJI_PATH` → their Fiji installation
   - `FRAMES_PATH` → their frames location

The `.env` file is NOT tracked by git, so everyone can have different paths.

See [TEAM_SETUP.md](TEAM_SETUP.md) for detailed team onboarding guide.

---

## 📁 Frame Path Examples

### Relative paths (from project root)
```bash
FRAMES_PATH=vid1_frames
FRAMES_PATH=data/batches/my_batch
```

### Absolute paths
```bash
FRAMES_PATH=/home/username/microscope_data/batch_001
FRAMES_PATH=/mnt/shared/lab_storage/experiments/2024-02
```

### Windows WSL paths
```bash
FRAMES_PATH=/mnt/c/Users/username/Documents/frames
FRAMES_PATH=/mnt/d/Research/CellTracking/frames
```

---

## 🔄 Processing Multiple Batches

### Incremental workflow
```bash
# First batch (creates new cells)
./run_test.sh --batch data/batches/frames_1_3 --clean --visualize

# Second batch (stitches to existing cells)
./run_test.sh --batch data/batches/frames_1_6 --visualize

# Third batch (continues tracking)
./run_test.sh --batch data/batches/frames_1_9 --export
```

### Switch between projects
```bash
# Update .env for project A
echo "FRAMES_PATH=/path/to/projectA/frames" >> .env
./run_test.sh --clean --visualize

# Or override for project B
./run_test.sh --batch /path/to/projectB/frames --clean --visualize
```

---

## 📊 Output Locations

After running the pipeline:

```
data/
  tracking.db           # SQLite database with all tracking data
  trackmate_runs/       # TrackMate CSV and XML outputs

output/
  visualizations/
    tracks.png          # Rendered track visualization
  exports/
    master_tracks.csv   # All cell positions
    cells_summary.csv   # Per-cell statistics
    events.csv          # Division/merge events
```

---

## 🔍 Querying Results

### View in database
```bash
sqlite3 data/tracking.db "SELECT * FROM cells;"
sqlite3 data/tracking.db "SELECT * FROM points LIMIT 20;"
```

### View visualization
```bash
# Linux
xdg-open output/visualizations/tracks.png

# Windows WSL
explorer.exe output/visualizations/tracks.png
```

### View CSV exports
```bash
cat output/exports/cells_summary.csv
column -t -s, output/exports/master_tracks.csv | less -S
```

---

## 🆘 Troubleshooting

### "FIJI_PATH not set"
→ Set in `.env` file or export manually:
```bash
export FIJI_PATH=/home/username/Fiji/fiji-linux-x64
```

### "Batch directory does not exist"
→ Check path in `.env` or use absolute path:
```bash
./run_test.sh --batch /absolute/path/to/frames
```

### "Unrecognized runtime argument: --run"
→ Fixed! Make sure you pulled the latest code with updated `fiji_runner.py`

### Need different parameters?
→ Edit `src/config.py` to tune TrackMate settings

---

## 📚 Documentation Index

- **This File**: Quick usage reference
- **TEAM_SETUP.md**: Team onboarding and collaboration
- **ENV_SETUP.md**: Detailed .env configuration
- **QUICKSTART.md**: First-time setup guide
- **README_PIPELINE.md**: Full technical documentation
- **PROJECT_SUMMARY.md**: Architecture and design decisions

---

## ⚡ Common Workflows

### Daily testing workflow
```bash
# Activate venv (if not already)
source venv/bin/activate

# Run with default settings from .env
./run_test.sh --visualize

# Check results
sqlite3 data/tracking.db "SELECT COUNT(*) FROM cells;"
```

### Processing new captures
```bash
# Copy frames from capture tool
cp ~/Documents/OncoTrackSnaps/*.png data/batches/new_batch/

# Process
./run_test.sh --batch data/batches/new_batch --visualize --export
```

### Parameter tuning
```bash
# Edit parameters
nano src/config.py

# Test with small batch
./run_test.sh --clean --visualize

# Check if detections improved
xdg-open output/visualizations/tracks.png
```

---

**Need help?** Check the documentation files or run:
```bash
./run_test.sh --help
./verify_setup.sh
```
