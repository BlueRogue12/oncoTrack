# OncoTrack

Incremental cell tracking pipeline using Fiji/TrackMate headless for detection and Python for orchestration.

## Quick Start

```bash
# 1. Run setup (creates .env file and installs dependencies)
./setup_env.sh

# 2. Configure your paths in .env
nano .env   # Set FIJI_PATH and FRAMES_PATH

# 3. Test with your data
./run_test.sh --visualize --export
```

See [ENV_SETUP.md](ENV_SETUP.md) for configuration details, [TEAM_SETUP.md](TEAM_SETUP.md) for team onboarding, and [QUICKSTART.md](QUICKSTART.md) for full setup guide.

## Components

### 1. Frame Capture (Existing Tool)

Qt GUI for capturing microscope frames from screen regions.

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install PySide6
python tools/frameCapture.py
```

**Status**: Complete, do not modify

### 2. Tracking Pipeline (New)

Incremental cell tracking with persistent IDs and SQLite storage.

```bash
# Install dependencies
pip install -r requirements.txt

# Set Fiji path
export FIJI_PATH=/path/to/fiji/ImageJ-linux64

# Run pipeline
python -m src.main --batch data/batches/frames_1_3 --visualize --export
```

**Status**: Complete implementation

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - 5-minute setup guide
- [CAPTURE_WORKFLOW.md](CAPTURE_WORKFLOW.md) - Frame capture & processing workflow
- [ENV_SETUP.md](ENV_SETUP.md) - Environment configuration guide
- [TEAM_SETUP.md](TEAM_SETUP.md) - Team onboarding guide
- [README_PIPELINE.md](README_PIPELINE.md) - Full pipeline documentation
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Technical overview

## Architecture

```
Frame Producer → Batch Directories → Tracking Pipeline → SQLite + Visualizations
(frameCapture.py)                    (src/main.py)
```

## Features

- ✅ Incremental processing with overlap window
- ✅ Persistent cell IDs via stitching
- ✅ Fiji/TrackMate headless execution
- ✅ SQLite persistence
- ✅ Track visualization with OpenCV
- ✅ Master CSV export
- ✅ Unit tests
- ✅ Comprehensive documentation
