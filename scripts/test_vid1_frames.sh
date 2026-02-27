#!/bin/bash
# Quick test script for vid1_frames

set -e

echo "=========================================="
echo "Testing OncoTrack Pipeline"
echo "=========================================="
echo ""

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "✓ Loading configuration from .env file"
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    echo ""
fi

# Use FRAMES_PATH from .env, or default to vid1_frames
BATCH_PATH="${FRAMES_PATH:-vid1_frames}"
echo "Using frames from: $BATCH_PATH"
echo ""

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Virtual environment not active"
    echo "Attempting to activate..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo "✓ Virtual environment activated"
    else
        echo "❌ Virtual environment not found. Run: python -m venv venv"
        exit 1
    fi
fi

# Check FIJI_PATH
if [[ -z "$FIJI_PATH" ]]; then
    echo ""
    echo "⚠️  WARNING: FIJI_PATH not set"
    echo "The pipeline will fail at the TrackMate step without Fiji."
    echo ""
    echo "To fix, run:"
    echo "  export FIJI_PATH=/path/to/fiji/ImageJ-linux64"
    echo ""
    echo "Press Enter to continue anyway, or Ctrl+C to abort..."
    read
fi

# Clean previous outputs (optional)
echo "Cleaning previous test outputs..."
rm -rf data/tracking.db data/trackmate_runs output
echo "✓ Cleaned"
echo ""

# Run the pipeline
echo "Running pipeline on vid1_frames..."
echo ""

python -m src.main \
    --batch "$BATCH_PATH" \
    --visualize \
    --export \
    --output-dir output \
    --log-level INFO

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Test completed successfully!"
    echo ""
    echo "Check outputs:"
    echo "  📊 Database: data/tracking.db"
    echo "  🎨 Visualization: output/visualizations/tracks.png"
    echo "  📄 CSV exports: output/exports/*.csv"
    echo "  🔬 TrackMate data: data/trackmate_runs/"
    echo ""
    echo "To query the database:"
    echo "  sqlite3 data/tracking.db 'SELECT * FROM cells;'"
else
    echo "❌ Test failed with exit code $EXIT_CODE"
    echo ""
    echo "Common issues:"
    echo "  - FIJI_PATH not set or incorrect"
    echo "  - Missing Python dependencies (run: pip install -r requirements.txt)"
    echo "  - Fiji/TrackMate not installed properly"
fi
echo "=========================================="

exit $EXIT_CODE
