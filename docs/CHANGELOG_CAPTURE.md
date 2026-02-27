# Capture Configuration Changes

## Summary

Added `CAPTURE_OUTPUT_DIR` environment variable to support flexible frame capture and processing workflow during development.

## Changes Made

### 1. New Environment Variable

**`CAPTURE_OUTPUT_DIR`** - Where `frameCapture.py` saves screenshots

```bash
# Development (default)
CAPTURE_OUTPUT_DIR=captures

# Production (future)
CAPTURE_OUTPUT_DIR=/mnt/shared/microscope/live_captures
```

### 2. Directory Structure

Created `captures/` directory:
- Used for local screenshot storage during development
- Gitignored (not committed)
- Each developer has their own local captures

### 3. Updated Files

#### `.env.example`
- Added `CAPTURE_OUTPUT_DIR` with documentation
- Reorganized into sections (Fiji, Capture/Processing, Advanced)
- Added examples for development vs production

#### `.env`
- Added `CAPTURE_OUTPUT_DIR=captures`

#### `.gitignore`
- Added `captures/` directory

#### `README.md`
- Added link to `CAPTURE_WORKFLOW.md`

#### `TEAM_SETUP.md`
- Added reference to capture workflow documentation

### 4. New Documentation

**`CAPTURE_WORKFLOW.md`** - Comprehensive guide covering:
- Development vs production workflow
- Configuration variables explained
- Typical development scenarios
- Team collaboration guidelines
- Directory structure
- Common questions

## Workflow

### Development Mode (Current)

```
frameCapture.py → captures/ (local, gitignored)
                     ↓ (manually switch FRAMES_PATH)
                  FRAMES_PATH → Tracking Pipeline
```

### Production Mode (Future)

```
frameCapture.py → CAPTURE_OUTPUT_DIR (shared location)
                     ║
                     ║ (same location)
                     ║
                  FRAMES_PATH → Tracking Pipeline
```

## Testing Scenarios

### Test with Sample Data (Recommended)
```bash
FRAMES_PATH=vid1_frames
./run_test.sh --visualize --export
```

### Test with Your Captures
```bash
# 1. Capture frames
python tools/frameCapture.py
# (saves to captures/)

# 2. Process them
FRAMES_PATH=captures
./run_test.sh --visualize --export
```

### Full Integration Test
```bash
# Both point to same location
CAPTURE_OUTPUT_DIR=test_integration
FRAMES_PATH=test_integration

# Capture → Process
python tools/frameCapture.py
./run_test.sh --batch test_integration --visualize
```

## Benefits

1. **Flexible Development**: Each developer can configure their own capture location
2. **Clean Git History**: Captures are not committed (gitignored)
3. **Sample Data Preserved**: `vid1_frames/` remains committed for testing
4. **Production Ready**: Easy transition to shared storage in production
5. **Team Friendly**: Clear separation between personal workspace and shared data

## Migration Notes

**No breaking changes** - existing `.env` files continue to work. The new `CAPTURE_OUTPUT_DIR` is optional and only needed if you're using `frameCapture.py`.

## Next Steps

1. Update your `.env` if you plan to use frame capture:
   ```bash
   echo 'CAPTURE_OUTPUT_DIR=captures' >> .env
   ```

2. Read `CAPTURE_WORKFLOW.md` for detailed workflow explanation

3. Continue using `FRAMES_PATH` as before for processing
