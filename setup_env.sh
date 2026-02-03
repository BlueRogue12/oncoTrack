#!/bin/bash
# One-time setup script for OncoTrack pipeline

set -e

echo "=========================================="
echo "OncoTrack Pipeline - Initial Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    echo "✓ .env file already exists"
else
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and set your FIJI_PATH"
    echo "   Current default: /home/phillip/Fiji/fiji-linux-x64"
    echo ""
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✓ Virtual environment already exists"
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Created virtual environment"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install/upgrade dependencies
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip > /dev/null
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Verify .env configuration
echo ""
echo "=========================================="
echo "Configuration Check"
echo "=========================================="

if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    
    if [ -n "$FIJI_PATH" ]; then
        echo "✓ FIJI_PATH is set: $FIJI_PATH"
        
        if [ -x "$FIJI_PATH" ]; then
            echo "✓ Fiji executable is accessible"
        else
            echo "⚠️  Warning: Fiji executable not found or not executable"
            echo "   Check your FIJI_PATH in .env file"
        fi
    else
        echo "⚠️  FIJI_PATH not set in .env file"
        echo "   Edit .env and set: FIJI_PATH=/path/to/fiji/executable"
    fi
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env file if needed: nano .env"
echo "  2. Run tests: ./test_vid1_frames.sh"
echo "  3. Or run directly: python -m src.main --batch vid1_frames_1-3 --visualize"
echo ""
echo "The virtual environment is now active."
echo "To deactivate, run: deactivate"
