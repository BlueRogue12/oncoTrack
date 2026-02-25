# OncoTrack

Incremental cell tracking pipeline using Fiji/TrackMate headless for detection and Python for orchestration.

## Quick Start

```bash
# 1. Run setup (creates .env file and installs dependencies)
./scripts/setup_env.sh

# 2. Configure your paths in .env
nano .env   # Set FIJI_PATH and FRAMES_PATH

# 3. Test with your data
./scripts/run_test.sh --visualize --export
```

See [docs/ENV_SETUP.md](docs/ENV_SETUP.md) for configuration details, [docs/TEAM_SETUP.md](docs/TEAM_SETUP.md) for team onboarding, and [docs/QUICKSTART.md](docs/QUICKSTART.md) for full setup guide.

## Components

### 1. Frame Capture (Existing Tool)

Qt GUI for capturing microscope frames from screen regions.

**Installation:**
```bash
# Install just PySide6 for the capture tool
pip install PySide6

# Or install all project dependencies
pip install -r requirements.txt
```

**Run:**
```bash
python tools/frameCapture.py
```

**Output Location:**
Frames are automatically saved to `captures/` folder in the project root (gitignored).

**Status**: Complete, simplified for team use

### 2. Tracking Pipeline (New)

Incremental cell tracking with persistent IDs and SQLite storage.

```bash
# Install dependencies
pip install -r requirements.txt

# Set Fiji path in .env (or use environment variable)
nano .env

# Run pipeline on sample data
./scripts/run_test.sh --batch vid1_frames --visualize --export

# Or use Python directly
python -m src.main --batch vid1_frames --visualize --export
```

**Status**: Complete implementation

## Documentation

📚 **[Full Documentation →](docs/)**

Quick links:
- [docs/QUICKSTART.md](docs/QUICKSTART.md) - 5-minute setup guide
- [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) - Branching strategy and git best practices
- [docs/TEAM_SETUP.md](docs/TEAM_SETUP.md) - Team onboarding guide
- [docs/CAPTURE_WORKFLOW.md](docs/CAPTURE_WORKFLOW.md) - Frame capture & processing workflow
- [docs/README_PIPELINE.md](docs/README_PIPELINE.md) - Full pipeline documentation
- [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md) - Technical overview

## Scripts

🔧 **[Utility Scripts →](scripts/)**

- [scripts/setup_env.sh](scripts/setup_env.sh) - One-time environment setup
- [scripts/run_test.sh](scripts/run_test.sh) - Run pipeline tests
- [scripts/verify_setup.sh](scripts/verify_setup.sh) - Verify installation

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
