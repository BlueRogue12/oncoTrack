#!/bin/bash
# Flexible test script - uses .env defaults but allows command-line override

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OncoTrack Pipeline Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Load .env file if it exists
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Loading configuration from .env file${NC}"
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    echo ""
fi

# Parse command-line arguments
BATCH_PATH=""
VISUALIZE=""
EXPORT=""
CLEAN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --batch)
            BATCH_PATH="$2"
            shift 2
            ;;
        --visualize)
            VISUALIZE="--visualize"
            shift
            ;;
        --export)
            EXPORT="--export"
            shift
            ;;
        --clean)
            CLEAN="true"
            shift
            ;;
        --help)
            echo "Usage: ./run_test.sh [options]"
            echo ""
            echo "Options:"
            echo "  --batch PATH    Path to frames (default: from .env FRAMES_PATH)"
            echo "  --visualize     Generate visualization"
            echo "  --export        Export CSV files"
            echo "  --clean         Clean previous outputs before running"
            echo ""
            echo "Examples:"
            echo "  ./run_test.sh"
            echo "  ./run_test.sh --visualize --export"
            echo "  ./run_test.sh --batch data/batches/frames_1_6 --visualize"
            echo "  ./run_test.sh --batch /mnt/shared/my_frames --clean --export"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

# Use command-line batch path, or fall back to FRAMES_PATH from .env, or default
if [ -z "$BATCH_PATH" ]; then
    BATCH_PATH="${FRAMES_PATH:-vid1_frames}"
fi

echo "Configuration:"
echo "  Frames: $BATCH_PATH"
echo "  Fiji: ${FIJI_PATH:-not set}"
echo ""

# Check if batch path exists
if [ ! -d "$BATCH_PATH" ]; then
    echo -e "${RED}Error: Batch directory does not exist: $BATCH_PATH${NC}"
    exit 1
fi

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${RED}⚠️  Virtual environment not active${NC}"
    if [ -f "venv/bin/activate" ]; then
        echo "Activating virtual environment..."
        source venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo "Run: source venv/bin/activate"
        exit 1
    fi
fi
echo ""

# Check FIJI_PATH
if [[ -z "$FIJI_PATH" ]]; then
    echo -e "${RED}⚠️  WARNING: FIJI_PATH not set${NC}"
    echo "The pipeline will fail at the TrackMate step."
    echo "Set it in .env file or export FIJI_PATH=/path/to/fiji"
    echo ""
    echo "Press Enter to continue anyway, or Ctrl+C to abort..."
    read
fi

# Clean previous outputs if requested
if [ "$CLEAN" = "true" ]; then
    echo "Cleaning previous outputs..."
    rm -rf data/tracking.db data/trackmate_runs output
    echo -e "${GREEN}✓ Cleaned${NC}"
    echo ""
fi

# Run the pipeline
echo -e "${BLUE}Running pipeline...${NC}"
echo ""

python -m src.main \
    --batch "$BATCH_PATH" \
    $VISUALIZE \
    $EXPORT \
    --output-dir output \
    --log-level INFO

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Pipeline completed successfully!${NC}"
    echo ""
    echo "Outputs:"
    echo "  📊 Database: data/tracking.db"
    if [[ -n "$VISUALIZE" ]]; then
        echo "  🎨 Visualization: output/visualizations/tracks.png"
    fi
    if [[ -n "$EXPORT" ]]; then
        echo "  📄 CSV exports: output/exports/*.csv"
    fi
    echo "  🔬 TrackMate data: data/trackmate_runs/"
    echo ""
    echo "Query the database:"
    echo "  sqlite3 data/tracking.db 'SELECT * FROM cells;'"
else
    echo -e "${RED}❌ Pipeline failed with exit code $EXIT_CODE${NC}"
fi
echo "=========================================="

exit $EXIT_CODE
