#!/bin/bash
# Setup script to configure FIJI_PATH for OncoTrack pipeline

# Your Fiji installation (WSL Linux path)
export FIJI_PATH="/home/phillip/Fiji/fiji-linux-x64"

echo "✓ FIJI_PATH set to: $FIJI_PATH"

# Test if Fiji executable exists and is executable
if [ -x "$FIJI_PATH" ]; then
    echo "✓ Fiji executable found and is executable"
    
    # Test Fiji version
    echo ""
    echo "Testing Fiji installation..."
    $FIJI_PATH --version 2>&1 | head -5
    
    echo ""
    echo "✅ Fiji is ready!"
    echo ""
    echo "To make this permanent, add to your ~/.bashrc:"
    echo "  echo 'export FIJI_PATH=\"/home/phillip/Fiji/fiji-linux-x64\"' >> ~/.bashrc"
    echo ""
    echo "Now you can run the pipeline:"
    echo "  ./test_vid1_frames.sh"
    echo "  or"
    echo "  python -m src.main --batch vid1_frames_1-3 --visualize --export"
else
    echo "❌ Error: Fiji executable not found or not executable at: $FIJI_PATH"
    echo ""
    echo "Available executables in /home/phillip/Fiji:"
    ls -lh /home/phillip/Fiji/fiji*
fi
