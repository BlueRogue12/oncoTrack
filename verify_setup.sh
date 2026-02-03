#!/bin/bash
# Verification script to check if the pipeline is correctly set up

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OncoTrack Pipeline Setup Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

ERRORS=0
WARNINGS=0

# Function to check command
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "${RED}✗${NC} $1 not found"
        return 1
    fi
}

# Function to check file
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 missing"
        return 1
    fi
}

# Function to check directory
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/ missing"
        return 1
    fi
}

echo "=== System Requirements ==="
echo ""

# Python version
if check_command python; then
    VERSION=$(python --version 2>&1 | cut -d' ' -f2)
    MAJOR=$(echo $VERSION | cut -d'.' -f1)
    MINOR=$(echo $VERSION | cut -d'.' -f2)
    
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
        echo -e "  Python version: ${GREEN}$VERSION${NC}"
    else
        echo -e "  ${RED}Python 3.11+ required, found $VERSION${NC}"
        ((ERRORS++))
    fi
else
    echo -e "  ${RED}Python not found${NC}"
    ((ERRORS++))
fi

echo ""

# Fiji
if [ -z "$FIJI_PATH" ]; then
    echo -e "${YELLOW}⚠${NC} FIJI_PATH environment variable not set"
    echo "  Set with: export FIJI_PATH=/path/to/fiji/executable"
    ((WARNINGS++))
else
    if [ -x "$FIJI_PATH" ]; then
        echo -e "${GREEN}✓${NC} FIJI_PATH set and executable"
        echo "  Path: $FIJI_PATH"
    else
        echo -e "${RED}✗${NC} FIJI_PATH set but not executable: $FIJI_PATH"
        ((ERRORS++))
    fi
fi

echo ""
echo "=== Python Dependencies ==="
echo ""

# Check if venv exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment exists"
else
    echo -e "${YELLOW}⚠${NC} Virtual environment not found"
    echo "  Create with: python -m venv venv"
    ((WARNINGS++))
fi

# Check if packages are installed
python -c "import cv2" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} opencv-python installed"
else
    echo -e "${RED}✗${NC} opencv-python not installed"
    ((ERRORS++))
fi

python -c "import numpy" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} numpy installed"
else
    echo -e "${RED}✗${NC} numpy not installed"
    ((ERRORS++))
fi

python -c "import pytest" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} pytest installed"
else
    echo -e "${YELLOW}⚠${NC} pytest not installed (optional for testing)"
    ((WARNINGS++))
fi

echo ""
echo "=== Directory Structure ==="
echo ""

check_dir "src" || ((ERRORS++))
check_dir "fiji_scripts" || ((ERRORS++))
check_dir "tests" || ((ERRORS++))
check_dir "data/batches" || ((ERRORS++))
check_dir "tools" || ((ERRORS++))

echo ""
echo "=== Core Python Modules ==="
echo ""

check_file "src/__init__.py" || ((ERRORS++))
check_file "src/config.py" || ((ERRORS++))
check_file "src/store.py" || ((ERRORS++))
check_file "src/frame_ingest.py" || ((ERRORS++))
check_file "src/fiji_runner.py" || ((ERRORS++))
check_file "src/parse_trackmate_outputs.py" || ((ERRORS++))
check_file "src/stitcher.py" || ((ERRORS++))
check_file "src/export.py" || ((ERRORS++))
check_file "src/visualize.py" || ((ERRORS++))
check_file "src/main.py" || ((ERRORS++))

echo ""
echo "=== Fiji Scripts ==="
echo ""

check_file "fiji_scripts/run_trackmate_tail.groovy" || ((ERRORS++))

echo ""
echo "=== Tests ==="
echo ""

check_file "tests/test_stitcher.py" || ((ERRORS++))

echo ""
echo "=== Documentation ==="
echo ""

check_file "README.md" || ((ERRORS++))
check_file "README_PIPELINE.md" || ((ERRORS++))
check_file "QUICKSTART.md" || ((ERRORS++))
check_file "PROJECT_SUMMARY.md" || ((ERRORS++))
check_file "requirements.txt" || ((ERRORS++))

echo ""
echo "=== Sample Data ==="
echo ""

if [ -d "data/batches/frames_1_3" ]; then
    COUNT=$(find data/batches/frames_1_3 -name "*.png" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓${NC} Sample frames found ($COUNT frames)"
    else
        echo -e "${YELLOW}⚠${NC} No frames in data/batches/frames_1_3"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} Sample batch directory not found"
    ((WARNINGS++))
fi

echo ""
echo "=== Summary ==="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Activate virtual environment: source venv/bin/activate"
    echo "  2. Run tests: pytest tests/"
    echo "  3. Process sample data: ./run_pipeline.sh --batch data/batches/frames_1_3 --visualize"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Setup complete with $WARNINGS warning(s)${NC}"
    echo ""
    echo "Fix warnings with:"
    echo "  - Set FIJI_PATH: export FIJI_PATH=/path/to/fiji/executable"
    echo "  - Create venv: python -m venv venv && source venv/bin/activate"
    echo "  - Install deps: pip install -r requirements.txt"
    exit 0
else
    echo -e "${RED}✗ Setup incomplete: $ERRORS error(s), $WARNINGS warning(s)${NC}"
    echo ""
    echo "Fix errors by:"
    echo "  - Installing Python 3.11+"
    echo "  - Installing dependencies: pip install -r requirements.txt"
    echo "  - Ensuring all files are present"
    exit 1
fi
