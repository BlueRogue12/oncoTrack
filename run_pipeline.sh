#!/bin/bash
# Convenience script to run the tracking pipeline

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OncoTrack Incremental Tracking Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Load .env file if it exists
if [ -f ".env" ]; then
    echo -e "${GREEN}Loading configuration from .env file${NC}"
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    echo ""
fi

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${RED}Warning: Virtual environment not activated${NC}"
    echo "Run: source venv/bin/activate"
    echo ""
fi

# Check if FIJI_PATH is set
if [[ -z "$FIJI_PATH" ]]; then
    echo -e "${RED}Warning: FIJI_PATH environment variable not set${NC}"
    echo "Set it in .env file or with: export FIJI_PATH=/path/to/fiji/executable"
    echo ""
fi

# Default values
BATCH=""
VISUALIZE=""
EXPORT=""
OUTPUT_DIR="output"
LOG_LEVEL="INFO"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --batch)
            BATCH="$2"
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
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./run_pipeline.sh --batch <path> [options]"
            echo ""
            echo "Options:"
            echo "  --batch PATH        Path to batch directory (required)"
            echo "  --visualize         Generate track visualization"
            echo "  --export            Export master CSV"
            echo "  --output-dir PATH   Output directory (default: output/)"
            echo "  --log-level LEVEL   Logging level (default: INFO)"
            echo ""
            echo "Example:"
            echo "  ./run_pipeline.sh --batch data/batches/frames_1_3 --visualize --export"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

# Check if batch is provided
if [[ -z "$BATCH" ]]; then
    echo -e "${RED}Error: --batch argument is required${NC}"
    echo "Run with --help for usage information"
    exit 1
fi

# Check if batch directory exists
if [[ ! -d "$BATCH" ]]; then
    echo -e "${RED}Error: Batch directory does not exist: $BATCH${NC}"
    exit 1
fi

echo -e "${GREEN}Processing batch: $BATCH${NC}"
echo ""

# Run the pipeline
python -m src.main \
    --batch "$BATCH" \
    $VISUALIZE \
    $EXPORT \
    --output-dir "$OUTPUT_DIR" \
    --log-level "$LOG_LEVEL"

EXIT_CODE=$?

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}✓ Pipeline completed successfully${NC}"
    echo ""
    echo "Outputs:"
    echo "  Database: data/tracking.db"
    if [[ -n "$VISUALIZE" ]]; then
        echo "  Visualization: $OUTPUT_DIR/visualizations/tracks.png"
    fi
    if [[ -n "$EXPORT" ]]; then
        echo "  Exports: $OUTPUT_DIR/exports/*.csv"
    fi
else
    echo -e "${RED}✗ Pipeline failed with exit code $EXIT_CODE${NC}"
fi

exit $EXIT_CODE
