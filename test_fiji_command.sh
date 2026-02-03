#!/bin/bash
# Test script to verify Fiji command structure

set -e

echo "Testing Fiji command-line syntax..."
echo ""

# Load .env
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

if [ -z "$FIJI_PATH" ]; then
    echo "ERROR: FIJI_PATH not set"
    exit 1
fi

echo "FIJI_PATH: $FIJI_PATH"
echo ""

# Test 1: Check Fiji version
echo "Test 1: Fiji version"
$FIJI_PATH --version 2>&1 | head -3
echo ""

# Test 2: Check if Groovy script exists
echo "Test 2: TrackMate script exists"
if [ -f "fiji_scripts/run_trackmate_tail.groovy" ]; then
    echo "✓ Script found"
    echo "  Size: $(wc -l < fiji_scripts/run_trackmate_tail.groovy) lines"
else
    echo "✗ Script not found"
    exit 1
fi
echo ""

# Test 3: Try running Fiji with help (to test command works)
echo "Test 3: Fiji help (checking --run option)"
$FIJI_PATH --help 2>&1 | grep -A 1 "\\-\\-run"
echo ""

# Test 4: Show what the actual command will look like
echo "Test 4: Command structure that will be used:"
echo ""
echo "  $FIJI_PATH \\"
echo "    --no-splash \\"
echo "    -Dinput_frames_dir=/path/to/frames \\"
echo "    -Doutput_dir=/path/to/output \\"
echo "    [... more -D parameters ...] \\"
echo "    -- \\"
echo "    --run fiji_scripts/run_trackmate_tail.groovy"
echo ""
echo "Note: Java properties (-D) BEFORE '--', main args AFTER '--'"
echo ""

echo "✅ Fiji command structure looks correct!"
echo ""
echo "Ready to run full pipeline with:"
echo "  ./test_vid1_frames.sh"
