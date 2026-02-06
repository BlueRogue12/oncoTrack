# Frame Capture & Processing Workflow

## Overview

OncoTrack has two main components that work together:

1. **Frame Capture (Frontend)** - `tools/frameCapture.py` - Qt GUI for capturing microscope frames
2. **Tracking Pipeline (Backend)** - TrackMate + Python - Processes frames and tracks cells

## Development vs Production

### Development Mode (Current)

During development, these components run **separately**:

```
┌─────────────────────┐
│  frameCapture.py    │  ← Qt GUI captures screenshots
│  (PRODUCER)         │
└──────────┬──────────┘
           │ saves to
           ▼
    captures/          ← Local folder (gitignored)
           │
           │ (manually switch FRAMES_PATH in .env)
           │
           ▼
┌─────────────────────┐
│  Tracking Pipeline  │  ← Reads frames, runs TrackMate
│  (CONSUMER)         │
└─────────────────────┘
```

### Production Mode (Future)

In production, the output of capture becomes the input of tracking automatically:

```
┌─────────────────────┐
│  frameCapture.py    │
└──────────┬──────────┘
           │ saves to shared location
           ▼
    CAPTURE_OUTPUT_DIR  ← Network drive or shared folder
           ║
           ║ (same location)
           ║
           ▼
    FRAMES_PATH        ← Pipeline watches this directory
           │
           ▼
┌─────────────────────┐
│  Tracking Pipeline  │
└─────────────────────┘
```

## Configuration in `.env`

### `CAPTURE_OUTPUT_DIR`

**Purpose**: Where `frameCapture.py` saves screenshots

**Development**: `captures/` (inside project, gitignored)
- Each team member has their own local captures
- Not committed to git
- Can be deleted/recreated anytime

**Production**: Shared network location
```bash
CAPTURE_OUTPUT_DIR=/mnt/shared/microscope/live_captures
```

### `FRAMES_PATH`

**Purpose**: Which frames the tracking pipeline processes

**Development Options**:

1. **Test with sample data** (recommended for initial testing):
   ```bash
   FRAMES_PATH=vid1_frames_1-3
   ```
   - Uses committed sample frames
   - Everyone on the team has the same data
   - Good for verifying pipeline works correctly

2. **Test with your own captures**:
   ```bash
   FRAMES_PATH=captures
   ```
   - Uses frames you captured locally
   - Good for testing the full workflow
   - Each team member can have different data

3. **Test with custom batches**:
   ```bash
   FRAMES_PATH=data/batches/my_experiment
   ```

**Production**: Same as `CAPTURE_OUTPUT_DIR`
```bash
CAPTURE_OUTPUT_DIR=/mnt/shared/microscope/live_captures
FRAMES_PATH=/mnt/shared/microscope/live_captures
```

## Typical Development Workflow

### Scenario 1: Testing the Pipeline (No Capture)

```bash
# 1. Use committed sample data
FRAMES_PATH=vid1_frames_1-3

# 2. Run pipeline
./run_test.sh --clean --visualize --export

# 3. Verify results in output/
```

**Use this when**: Testing pipeline logic, stitching, visualization

### Scenario 2: Testing Frame Capture

```bash
# 1. Configure capture output
CAPTURE_OUTPUT_DIR=captures

# 2. Run frameCapture.py
python tools/frameCapture.py

# 3. Capture some frames using the GUI
# (frames saved to captures/)

# 4. Switch pipeline to use your captures
FRAMES_PATH=captures

# 5. Run pipeline
./run_test.sh --clean --visualize --export
```

**Use this when**: Testing the Qt GUI, verifying capture quality

### Scenario 3: Full Integration Test

```bash
# 1. Set both to same location
CAPTURE_OUTPUT_DIR=test_integration
FRAMES_PATH=test_integration

# 2. Create directory
mkdir -p test_integration

# 3. Run capture GUI
python tools/frameCapture.py
# (capture frames to test_integration/)

# 4. Run pipeline
./run_test.sh --clean --visualize --export
```

**Use this when**: Testing the full end-to-end workflow

## Team Collaboration

### What's Committed to Git

✅ **Committed** (everyone gets these):
- `vid1_frames_1-3/` - Sample cell images for testing
- `tools/frameCapture.py` - Frame capture GUI
- `src/` - Tracking pipeline code
- `.env.example` - Configuration template

❌ **Not Committed** (local to each developer):
- `captures/` - Your local screenshot captures
- `.env` - Your personal configuration
- `data/tracking.db` - Your local database
- `output/` - Your pipeline outputs

### Setup for New Team Member

```bash
# 1. Clone repo
git clone <repo-url>
cd oncoTrack

# 2. Run setup
./setup_env.sh

# 3. Edit .env with your Fiji path
# FIJI_PATH=/your/path/to/fiji

# 4. Test with sample data (no capture needed)
./run_test.sh --clean --visualize --export

# 5. (Optional) Test frame capture
python tools/frameCapture.py
```

## Directory Structure

```
oncoTrack/
├── tools/
│   └── frameCapture.py          ← Frame capture GUI (committed)
│
├── vid1_frames_1-3/             ← Sample frames (committed)
│   ├── cell_00001.png
│   ├── cell_00002.png
│   └── cell_00003.png
│
├── captures/                    ← Local captures (gitignored)
│   ├── frame_001.png            ← Your screenshots go here
│   ├── frame_002.png
│   └── ...
│
├── data/
│   └── tracking.db              ← SQLite database (gitignored)
│
├── output/                      ← Pipeline results (gitignored)
│   ├── visualizations/
│   ├── exports/
│   └── trackmate_runs/
│
└── src/                         ← Pipeline code (committed)
    ├── main.py
    ├── fiji_runner.py
    └── ...
```

## Common Questions

### Q: Why are captures/ gitignored but vid1_frames_1-3/ is committed?

**A**: `vid1_frames_1-3/` is **sample data** for testing - everyone should have the same frames to verify the pipeline works correctly. `captures/` is your **personal workspace** for development - each person's captures are different and don't need to be shared.

### Q: Can I commit my captures for others to test with?

**A**: Yes! Create a new folder outside `captures/`:
```bash
mkdir -p data/batches/my_experiment
cp captures/*.png data/batches/my_experiment/
git add data/batches/my_experiment
git commit -m "Add experiment batch"
```

Then others can test with:
```bash
FRAMES_PATH=data/batches/my_experiment
```

### Q: How do I switch between sample data and my captures?

**A**: Just change `FRAMES_PATH` in your `.env`:

```bash
# Test with sample data
FRAMES_PATH=vid1_frames_1-3

# Test with your captures
FRAMES_PATH=captures
```

Or override on command line:
```bash
./run_test.sh --batch captures --clean
```

### Q: In production, how will this work?

**A**: Both variables will point to the same shared location:

```bash
# Production .env
CAPTURE_OUTPUT_DIR=/mnt/shared/microscope/live_captures
FRAMES_PATH=/mnt/shared/microscope/live_captures
```

The capture GUI saves to that location, and the pipeline watches that location. No manual switching needed.

### Q: Can I delete my captures/ folder?

**A**: Yes! It's just local scratch space. The pipeline doesn't depend on it. You can delete it anytime and recreate it by running `frameCapture.py` again.

## Summary

| Variable | Purpose | Development | Production |
|----------|---------|-------------|------------|
| `CAPTURE_OUTPUT_DIR` | Where screenshots are saved | `captures/` (local, gitignored) | `/mnt/shared/...` (network drive) |
| `FRAMES_PATH` | What the pipeline processes | `vid1_frames_1-3` (sample) or `captures/` (your data) | `/mnt/shared/...` (same as capture output) |

**Key Insight**: In development, these are **separate** (manual workflow). In production, they're the **same location** (automatic workflow).
