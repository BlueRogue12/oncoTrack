# Team Setup Guide

Guide for setting up the OncoTrack pipeline for your team with personalized configurations.

## 🎯 Quick Team Onboarding

### 1. Clone the Repository

```bash
git clone <repository-url>
cd oncoTrack
```

### 2. Run Setup Script

```bash
./setup_env.sh
```

This creates your personal `.env` file (not tracked by git).

### 3. Configure Your Paths

Edit `.env` file with your local settings:

```bash
nano .env
```

**Required settings:**
```bash
# Path to your Fiji installation
FIJI_PATH=/path/to/your/fiji/executable

# Path to your frames directory
FRAMES_PATH=path/to/your/frames
```

### 4. Test the Pipeline

```bash
# Use default from .env
./run_test.sh --visualize --export

# Or override with specific path
./run_test.sh --batch /path/to/specific/frames --visualize
```

---

## 📁 Frame Path Configuration

Each team member can have frames stored in different locations. Configure your `FRAMES_PATH` in `.env`:

### Common Scenarios

#### Scenario 1: Frames in Project Directory
```bash
# .env
FRAMES_PATH=vid1_frames_1-3
```

Run test:
```bash
./run_test.sh --visualize
```

#### Scenario 2: Frames in Data Directory
```bash
# .env
FRAMES_PATH=data/batches/experiment_001
```

Run test:
```bash
./run_test.sh --visualize
```

#### Scenario 3: Frames on Shared Network Drive
```bash
# .env (Linux/Mac)
FRAMES_PATH=/mnt/lab_storage/microscope/captures/2024-02-03

# .env (Windows WSL)
FRAMES_PATH=/mnt/c/SharedData/CellFrames
```

Run test:
```bash
./run_test.sh --visualize
```

#### Scenario 4: Override at Runtime
```bash
# Use .env default for most tests
./run_test.sh --visualize

# But override for a specific batch
./run_test.sh --batch /tmp/test_frames --visualize
```

---

## 🔧 Per-Developer Configuration Examples

### Developer: Phillip (Original)
```bash
# .env
FIJI_PATH=/home/phillip/Fiji/fiji-linux-x64
FRAMES_PATH=vid1_frames_1-3
```

### Developer: Sarah (Mac with external drive)
```bash
# .env
FIJI_PATH=/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx
FRAMES_PATH=/Volumes/ExternalDrive/cell_tracking/batch_001
```

### Developer: Mike (Windows WSL with shared folder)
```bash
# .env
FIJI_PATH=/home/mike/tools/Fiji/fiji-linux-x64
FRAMES_PATH=/mnt/c/Users/Mike/Documents/Research/Frames
```

### Developer: Lisa (Linux with lab server mount)
```bash
# .env
FIJI_PATH=/opt/fiji/ImageJ-linux64
FRAMES_PATH=/mnt/lab_server/experiments/lisa/2024_Q1/frames
```

---

## 🚀 Running the Pipeline

### Method 1: Use .env Default

```bash
# Uses FRAMES_PATH from .env
./run_test.sh --visualize --export
```

### Method 2: Override Path

```bash
# Override with specific path
./run_test.sh --batch data/batches/frames_1_6 --visualize
```

### Method 3: Direct Python Command

```bash
# Full control
python -m src.main \
    --batch /path/to/frames \
    --visualize \
    --export \
    --log-level DEBUG
```

---

## 🔄 Processing Multiple Batches

### Incremental Processing Workflow

```bash
# Process first batch (creates initial tracking data)
./run_test.sh --batch data/batches/frames_1_3 --visualize --clean

# Process second batch (incremental - stitches to existing cells)
./run_test.sh --batch data/batches/frames_1_6 --visualize

# Process third batch (incremental)
./run_test.sh --batch data/batches/frames_1_9 --visualize --export
```

### Switch Between Projects

```bash
# Project A
./run_test.sh --batch /mnt/shared/projectA/frames --clean --visualize

# Project B (separate database)
./run_test.sh --batch /mnt/shared/projectB/frames --clean --visualize
```

---

## 📝 Team .env Template

Save this as `.env` and customize for your machine:

```bash
# OncoTrack Pipeline Configuration

# ==== REQUIRED: Update these for your system ====

# Path to Fiji executable
# Linux: /path/to/fiji/ImageJ-linux64
# Mac: /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx
# Windows WSL: /home/username/Fiji/fiji-linux-x64
FIJI_PATH=/path/to/your/fiji/executable

# Default path to frames directory
# Can be relative to project root or absolute path
# Examples:
#   vid1_frames_1-3
#   data/batches/my_batch
#   /mnt/shared/microscope/captures
FRAMES_PATH=vid1_frames_1-3


# ==== OPTIONAL: Advanced configuration ====

# Override database path (default: data/tracking.db)
# DB_PATH=data/tracking.db

# Override output directory (default: output/)
# OUTPUT_DIR=output

# Logging level (default: INFO)
# Options: DEBUG, INFO, WARNING, ERROR
# LOG_LEVEL=INFO
```

---

## ✅ Verification Checklist

Before running the pipeline, verify:

- [ ] Python 3.11+ installed (`python --version`)
- [ ] Virtual environment created (`venv/` exists)
- [ ] Dependencies installed (`pip list | grep opencv`)
- [ ] `.env` file created and configured
- [ ] `FIJI_PATH` points to valid executable
- [ ] `FRAMES_PATH` directory exists and contains images
- [ ] Fiji TrackMate plugin installed

Run verification:
```bash
./verify_setup.sh
```

---

## 🆘 Common Team Issues

### Issue: "FIJI_PATH not set"

**Solution:** Each team member must set their own path in `.env`:
```bash
echo 'FIJI_PATH=/path/to/your/fiji' >> .env
```

### Issue: "Batch directory does not exist"

**Solution:** Check your `FRAMES_PATH` in `.env` or use `--batch` to override:
```bash
# Check what's configured
cat .env | grep FRAMES_PATH

# Or provide explicit path
./run_test.sh --batch /absolute/path/to/frames
```

### Issue: Different results between team members

**Possible causes:**
1. Different Fiji versions - check `fiji --version`
2. Different TrackMate parameters - check `src/config.py`
3. Different frame input - verify frame counts match

**Solution:** Document your versions:
```bash
echo "## My Setup" >> TEAM_NOTES.md
echo "- Fiji: $(fiji --version | head -1)" >> TEAM_NOTES.md
echo "- Python: $(python --version)" >> TEAM_NOTES.md
```

### Issue: Permission denied on shared drive

**Solution:** Check mount permissions:
```bash
# Test read access
ls -la /mnt/shared/frames

# Test write access (for output)
touch /mnt/shared/test.txt && rm /mnt/shared/test.txt
```

---

## 📊 Sharing Results

### Option 1: Share Database File

```bash
# Copy database to shared location
cp data/tracking.db /mnt/shared/results/tracking_$(date +%Y%m%d).db
```

### Option 2: Export CSV

```bash
# Run with export
./run_test.sh --batch data/batches/frames_1_9 --export

# Share CSV files
cp output/exports/*.csv /mnt/shared/results/
```

### Option 3: Share Visualization

```bash
# Generate visualization
./run_test.sh --batch data/batches/frames_1_9 --visualize

# Share image
cp output/visualizations/tracks.png /mnt/shared/results/tracks_$(date +%Y%m%d).png
```

---

## 🔐 Security & Privacy

**Important:**
- `.env` is in `.gitignore` and NOT committed to git
- Each developer has their own `.env` with personal paths
- `.env.example` IS committed as a template
- Never commit absolute paths or credentials to git

**To share configuration template:**
```bash
# Update the example file (this IS committed)
nano .env.example

# Team members copy it
cp .env.example .env
# Then customize their copy
```

---

## 📚 Additional Resources

- **Capture Workflow**: See `CAPTURE_WORKFLOW.md` - Understand frame capture vs processing
- **Setup Guide**: See `ENV_SETUP.md` - Environment configuration details
- **Quick Start**: See `QUICKSTART.md` - Get running in 5 minutes
- **Full Documentation**: See `README_PIPELINE.md` - Complete pipeline reference
- **Configuration Options**: See `src/config.py` - All tunable parameters
