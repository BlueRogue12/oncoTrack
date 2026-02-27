# Frame Capture Tool - Usage Guide

## Overview

`tools/frameCapture.py` is a Qt GUI tool for capturing microscope frames from screen regions. It now integrates with the `.env` configuration file to save frames to a configurable location.

## Configuration

### Using .env File (Recommended)

Set the output directory in your `.env` file:

```bash
# .env
CAPTURE_OUTPUT_DIR=captures
```

**Path options:**
- **Relative path**: `captures` → saves to `<project_root>/captures/`
- **Absolute path**: `/home/username/data/frames` → saves to that exact location
- **Windows**: `C:/Users/Name/captures` or `/mnt/c/Users/Name/captures` (WSL2)

### Without .env (Fallback)

If `CAPTURE_OUTPUT_DIR` is not set, frames are saved to:
- **Linux/macOS**: `~/Documents/OncoTrackSnaps/`
- **Windows**: `C:\Users\YourName\Documents\OncoTrackSnaps\`

## Installation

### Option 1: Full Project Setup (Recommended)

If you've already set up the tracking pipeline:

```bash
# Activate venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

# Dependencies already installed
python tools/frameCapture.py
```

### Option 2: Standalone Capture Tool

If you only want the capture tool (no tracking):

```bash
# Create venv for capture tool only
python -m venv capture_venv
source capture_venv/bin/activate  # Linux/Mac

# Install just PySide6
pip install PySide6

# Run
python tools/frameCapture.py
```

**Note:** The main `requirements.txt` includes all dependencies including PySide6 for the frame capture tool.

## Usage

### 1. Start the Capture Tool

```bash
# With venv activated
python tools/frameCapture.py
```

### 2. Select Capture Region

1. Click "Select Region" button
2. Click and drag to select the screen area containing cells
3. Release to confirm selection

### 3. Configure Capture Settings

- **Interval**: Time between captures (seconds)
- **Duration**: How long to capture (minutes)

### 4. Start Capturing

Click "Start Capture" to begin. Frames will be saved to `CAPTURE_OUTPUT_DIR`.

### 5. Verify Output

```bash
# Check where frames are being saved
ls -la captures/
# or
ls -la ~/Documents/OncoTrackSnaps/
```

## Integration with Tracking Pipeline

### Development Workflow

**Step 1: Capture frames**
```bash
# Configure in .env
CAPTURE_OUTPUT_DIR=captures

# Run capture tool
python tools/frameCapture.py
# (capture some frames to captures/)
```

**Step 2: Process frames**
```bash
# Point pipeline to captured frames
FRAMES_PATH=captures

# Run pipeline
./run_test.sh --batch captures --visualize --export
```

### Production Workflow

In production, both tools use the same directory:

```bash
# .env (production)
CAPTURE_OUTPUT_DIR=/mnt/shared/microscope/live_captures
FRAMES_PATH=/mnt/shared/microscope/live_captures
```

Capture tool saves frames → Pipeline automatically processes them from the same location.

## Platform-Specific Notes

### Linux/WSL2

```bash
# .env
CAPTURE_OUTPUT_DIR=captures                      # Relative to project
# or
CAPTURE_OUTPUT_DIR=/home/username/data/captures   # Absolute path
```

### macOS

```bash
# .env
CAPTURE_OUTPUT_DIR=captures                              # Relative to project
# or
CAPTURE_OUTPUT_DIR=/Users/sarah/Experiments/captures    # Absolute path
```

### Windows Native

```bash
# .env (use forward slashes)
CAPTURE_OUTPUT_DIR=captures                          # Relative to project
# or
CAPTURE_OUTPUT_DIR=C:/Users/Mike/Data/captures      # Absolute path
```

### Windows WSL2

```bash
# .env
CAPTURE_OUTPUT_DIR=captures                                 # Relative to project
# or
CAPTURE_OUTPUT_DIR=/mnt/c/Users/Mike/Data/captures         # Access Windows drive
```

## File Naming

Captured frames are named with timestamps:
```
cell_00001.png
cell_00002.png
cell_00003.png
...
```

Or with timestamps if configured:
```
capture_2026-02-03_14-30-01.png
capture_2026-02-03_14-30-11.png
...
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'PySide6'"

**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
# Or just PySide6 if you only need the capture tool:
pip install PySide6
```

### Issue: "ModuleNotFoundError: No module named 'dotenv'"

**Solution:** Either:
1. Install dotenv: `pip install python-dotenv`
2. Or use the default location (`~/Documents/OncoTrackSnaps/`) - tool will fallback automatically

### Issue: Frames not appearing in expected directory

**Check:**
1. Verify `.env` file exists in project root
2. Check `CAPTURE_OUTPUT_DIR` value: `cat .env | grep CAPTURE_OUTPUT_DIR`
3. Check tool output for actual save location
4. Verify directory permissions

### Issue: "Permission denied" when saving frames

**Solution:** Choose a directory where you have write permissions:
```bash
# .env
CAPTURE_OUTPUT_DIR=~/my_captures  # Your home directory (always writable)
```

## Testing Configuration

Test that configuration is loaded correctly:

```bash
# Activate venv
source venv/bin/activate

# Test path resolution
python3 -c "
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
capture_dir = os.environ.get('CAPTURE_OUTPUT_DIR', '').strip()
print(f'CAPTURE_OUTPUT_DIR: {capture_dir}')

if capture_dir:
    out = Path(capture_dir)
    if not out.is_absolute():
        out = Path('.') / capture_dir
    print(f'Resolved to: {out.absolute()}')
    print(f'Exists: {out.exists()}')
else:
    print('Using default: ~/Documents/OncoTrackSnaps')
"
```

## Summary

| Configuration | Capture Saves To | Pipeline Reads From |
|---------------|------------------|---------------------|
| Development | `CAPTURE_OUTPUT_DIR` (e.g., `captures/`) | `FRAMES_PATH` (e.g., `vid1_frames`) |
| Testing | `CAPTURE_OUTPUT_DIR=captures` | `FRAMES_PATH=captures` |
| Production | `CAPTURE_OUTPUT_DIR=/mnt/shared/...` | `FRAMES_PATH=/mnt/shared/...` (same) |

**Key Insight:** In development, capture and processing are separate (manual). In production, they point to the same location (automatic).

See `CAPTURE_WORKFLOW.md` for more details on the full workflow.
