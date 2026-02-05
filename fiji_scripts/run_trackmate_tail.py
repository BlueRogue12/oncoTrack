"""
TrackMate Headless Script for Incremental Cell Tracking (Jython/Python)

This script runs TrackMate in headless mode.
Parameters are read from a JSON config file to avoid command-line parsing issues.

Based on official TrackMate scripting documentation:
https://imagej.net/plugins/trackmate/scripting/scripting
"""

import sys
import os
import json
from ij import IJ
from ij import ImagePlus, ImageStack

from fiji.plugin.trackmate import Model
from fiji.plugin.trackmate import Settings
from fiji.plugin.trackmate import TrackMate
from fiji.plugin.trackmate import SelectionModel
from fiji.plugin.trackmate import Logger
from fiji.plugin.trackmate.detection import LogDetectorFactory
from fiji.plugin.trackmate.detection import DogDetectorFactory
from fiji.plugin.trackmate.tracking.jaqaman import SparseLAPTrackerFactory
from fiji.plugin.trackmate.io import TmXmlWriter

from java.io import File

print "=" * 60
print "TrackMate Headless Tracking"
print "=" * 60

# Load configuration from JSON file
# The config file is created by the Python wrapper in the output directory
# We need to search for it since Fiji may change the working directory

import glob

config_path = None

# Try common locations
search_paths = [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)),
    "/home/phillip/code/oncoTrack",
]

# Also search in data/trackmate_runs subdirectories
base_dir = "/home/phillip/code/oncoTrack/data/trackmate_runs"
if os.path.exists(base_dir):
    for run_dir in os.listdir(base_dir):
        search_paths.append(os.path.join(base_dir, run_dir))

for search_dir in search_paths:
    test_path = os.path.join(search_dir, "trackmate_config.json")
    if os.path.exists(test_path):
        config_path = test_path
        break

if config_path is None:
    print "ERROR: Could not find trackmate_config.json"
    print "Searched in:"
    for p in search_paths:
        print "  -", p
    print "Current working directory:", os.getcwd()
    sys.exit(1)

print "Loading config from:", config_path
with open(config_path, 'r') as f:
    config = json.load(f)

# Extract parameters from config
input_frames_dir = config['input_frames_dir']
output_dir = config['output_dir']
detector = config.get('detector', 'DOG_DETECTOR')
radius = float(config.get('radius', 5.0))
threshold = float(config.get('threshold', 5.0))
do_subpixel = bool(config.get('do_subpixel', True))
do_median = bool(config.get('do_median', False))
target_channel = int(config.get('target_channel', 1))
linking_max_distance = float(config.get('linking_max_distance', 15.0))
gap_closing_max_distance = float(config.get('gap_closing_max_distance', 15.0))
max_frame_gap = int(config.get('max_frame_gap', 2))
pixel_size = float(config.get('pixel_size', 1.0))
time_interval = float(config.get('time_interval', 1.0))

print "Input directory:", input_frames_dir
print "Output directory:", output_dir
print "Detector:", detector
print "Radius:", radius
print "Threshold:", threshold
print "=" * 60

# Create output directory
output_file = File(output_dir)
if not output_file.exists():
    output_file.mkdirs()
    print "Created output directory"

# Load images from directory
print "\nLoading frames from", input_frames_dir
input_folder = File(input_frames_dir)

if not input_folder.exists():
    print "ERROR: Input directory does not exist:", input_frames_dir
    sys.exit(1)

# Get list of image files
image_files = []
for f in input_folder.listFiles():
    name = f.getName().lower()
    if name.endswith(".png") or name.endswith(".tif") or name.endswith(".tiff") or name.endswith(".jpg"):
        image_files.append(f)

if len(image_files) == 0:
    print "ERROR: No image files found in", input_frames_dir
    sys.exit(1)

# Sort files by name
image_files = sorted(image_files, key=lambda x: x.getName())
print "Found", len(image_files), "image files"

# Load first image to get dimensions
first_imp = IJ.openImage(image_files[0].getAbsolutePath())
if first_imp is None:
    print "ERROR: Could not load first image:", image_files[0].getAbsolutePath()
    sys.exit(1)

# Convert to grayscale if needed (TrackMate requires grayscale)
if first_imp.getType() == ImagePlus.COLOR_RGB:
    print "Converting RGB images to grayscale..."
    IJ.run(first_imp, "8-bit", "")

width = first_imp.getWidth()
height = first_imp.getHeight()
print "Image dimensions:", width, "x", height
print "Image type:", first_imp.getType()

# Build image stack
stack = ImageStack(width, height)
for img_file in image_files:
    print "Loading:", img_file.getName()
    imp = IJ.openImage(img_file.getAbsolutePath())
    if imp is not None:
        # Convert to grayscale if it's RGB
        if imp.getType() == ImagePlus.COLOR_RGB:
            IJ.run(imp, "8-bit", "")
        stack.addSlice(img_file.getName(), imp.getProcessor())
    else:
        print "WARNING: Could not load", img_file.getName()

# Create ImagePlus from stack
imp = ImagePlus("TrackMate Input Stack", stack)
print "Created stack with", stack.getSize(), "frames"

# Get calibration from image
cal = imp.getCalibration()

# ----------------------------
# Create the model object
# ----------------------------
model = Model()

# Set logger
model.setLogger(Logger.IJ_LOGGER)

# ----------------------------
# Prepare settings object
# ----------------------------
settings = Settings(imp)

# Configure image calibration
settings.dx = pixel_size
settings.dy = pixel_size
settings.dz = 1.0
settings.dt = time_interval

# Field of view is automatically set from the image
# (xstart, ystart, etc. are read-only in newer TrackMate versions)

print "\nConfiguring detector..."
# Configure detector
if detector == "LOG_DETECTOR":
    settings.detectorFactory = LogDetectorFactory()
else:
    settings.detectorFactory = DogDetectorFactory()

settings.detectorSettings = {
    'DO_SUBPIXEL_LOCALIZATION': do_subpixel,
    'RADIUS': radius,
    'TARGET_CHANNEL': target_channel,
    'THRESHOLD': threshold,
    'DO_MEDIAN_FILTERING': do_median,
}

print "Detector:", settings.detectorFactory
print "  Radius:", radius
print "  Threshold:", threshold
print "  Subpixel:", do_subpixel

# Configure tracker
print "\nConfiguring LAP tracker..."
settings.trackerFactory = SparseLAPTrackerFactory()
settings.trackerSettings = settings.trackerFactory.getDefaultSettings()
settings.trackerSettings['LINKING_MAX_DISTANCE'] = linking_max_distance
settings.trackerSettings['GAP_CLOSING_MAX_DISTANCE'] = gap_closing_max_distance
settings.trackerSettings['MAX_FRAME_GAP'] = max_frame_gap
settings.trackerSettings['ALLOW_GAP_CLOSING'] = True
settings.trackerSettings['ALLOW_TRACK_SPLITTING'] = True
settings.trackerSettings['ALLOW_TRACK_MERGING'] = False
settings.trackerSettings['SPLITTING_MAX_DISTANCE'] = linking_max_distance

print "Tracker: LAP"
print "  Linking max distance:", linking_max_distance
print "  Gap closing max distance:", gap_closing_max_distance
print "  Max frame gap:", max_frame_gap

# ----------------------------
# Instantiate plugin
# ----------------------------
print "\n" + "=" * 60
print "Running TrackMate..."
print "=" * 60

trackmate = TrackMate(model, settings)

# Check configuration
ok = trackmate.checkInput()
if not ok:
    print "ERROR: Configuration check failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

# Execute detection
print "\n1. Detecting spots..."
ok = trackmate.execDetection()
if not ok:
    print "ERROR: Detection failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

print "   Detected", model.getSpots().getNSpots(False), "spots"

# Execute initial spot filtering
print "\n2. Initial spot filtering..."
ok = trackmate.execInitialSpotFiltering()
if not ok:
    print "ERROR: Initial filtering failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

print "   After filtering:", model.getSpots().getNSpots(True), "spots"

# Compute spot features
print "\n3. Computing spot features..."
ok = trackmate.computeSpotFeatures(True)
if not ok:
    print "ERROR: Spot feature computation failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

# Execute spot filtering
print "\n4. Final spot filtering..."
ok = trackmate.execSpotFiltering(True)
if not ok:
    print "ERROR: Spot filtering failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

# Execute tracking
print "\n5. Tracking spots..."
ok = trackmate.execTracking()
if not ok:
    print "ERROR: Tracking failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

print "   Found", model.getTrackModel().nTracks(False), "tracks"

# Compute track features
print "\n6. Computing track features..."
ok = trackmate.computeTrackFeatures(True)
if not ok:
    print "ERROR: Track feature computation failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

# Execute track filtering
print "\n7. Final track filtering..."
ok = trackmate.execTrackFiltering(True)
if not ok:
    print "ERROR: Track filtering failed"
    print trackmate.getErrorMessage()
    sys.exit(1)

print "\n" + "=" * 60
print "Tracking completed successfully!"
print "Final counts:"
print "  Spots:", model.getSpots().getNSpots(True)
print "  Tracks:", model.getTrackModel().nTracks(True)
print "=" * 60

# ----------------------------
# Export results
# ----------------------------

print "\nExporting results..."

# Export TrackMate XML file
print "1. Exporting TrackMate XML..."
xml_file = File(output_dir, "trackmate.xml")
writer = TmXmlWriter(xml_file)
writer.appendModel(model)
writer.appendSettings(settings)
writer.writeToFile()
print "   Saved:", xml_file.getAbsolutePath()

# Export spots CSV
print "2. Exporting spots.csv..."
spots_file = File(output_dir, "spots.csv")
spots_writer = open(spots_file.getAbsolutePath(), 'w')
spots_writer.write("SPOT_ID,FRAME,POSITION_X,POSITION_Y,QUALITY,RADIUS\n")

spot_id = 0
for frame in range(stack.getSize()):
    spots_in_frame = model.getSpots().iterable(frame, False)
    if spots_in_frame is not None:
        for spot in spots_in_frame:
            spots_writer.write("%d,%d,%.4f,%.4f,%.4f,%.4f\n" % (
                spot_id,
                frame,
                spot.getDoublePosition(0),
                spot.getDoublePosition(1),
                spot.getFeature('QUALITY'),
                spot.getFeature('RADIUS')
            ))
            spot_id += 1

spots_writer.close()
print "   Saved:", spots_file.getAbsolutePath()
print "   Total spots exported:", spot_id

# Export tracks and edges
print "3. Exporting tracks.csv and edges.csv..."
tracks_file = File(output_dir, "tracks.csv")
edges_file = File(output_dir, "edges.csv")
spots_in_tracks_file = File(output_dir, "spots_in_tracks.csv")

tracks_writer = open(tracks_file.getAbsolutePath(), 'w')
edges_writer = open(edges_file.getAbsolutePath(), 'w')
spots_in_tracks_writer = open(spots_in_tracks_file.getAbsolutePath(), 'w')

tracks_writer.write("TRACK_ID,NUMBER_SPOTS,TRACK_DURATION,TRACK_START,TRACK_STOP,TRACK_DISPLACEMENT\n")
edges_writer.write("TRACK_ID,SPOT_SOURCE_ID,SPOT_TARGET_ID,LINK_COST,EDGE_TIME,EDGE_X_LOCATION,EDGE_Y_LOCATION,VELOCITY,DISPLACEMENT\n")
spots_in_tracks_writer.write("TRACK_ID,SPOT_ID,FRAME,POSITION_X,POSITION_Y,QUALITY,RADIUS\n")

# Build spot ID mapping
spot_to_id = {}
spot_id = 0
for frame in range(stack.getSize()):
    spots_in_frame = model.getSpots().iterable(frame, False)
    if spots_in_frame is not None:
        for spot in spots_in_frame:
            spot_to_id[spot] = spot_id
            spot_id += 1

# Export track data
track_model = model.getTrackModel()
track_ids = track_model.trackIDs(True)

for track_id in track_ids:
    # Get spots in track
    track_spots = list(track_model.trackSpots(track_id))
    track_spots.sort(key=lambda s: s.getFeature('FRAME'))
    
    num_spots = len(track_spots)
    
    if num_spots > 0:
        first_spot = track_spots[0]
        last_spot = track_spots[-1]
        
        track_start = first_spot.getFeature('FRAME') * time_interval
        track_stop = last_spot.getFeature('FRAME') * time_interval
        track_duration = track_stop - track_start
        
        # Calculate displacement
        x0 = first_spot.getDoublePosition(0)
        y0 = first_spot.getDoublePosition(1)
        xN = last_spot.getDoublePosition(0)
        yN = last_spot.getDoublePosition(1)
        displacement = ((xN - x0)**2 + (yN - y0)**2)**0.5
        
        # Write track info
        tracks_writer.write("%d,%d,%.4f,%.4f,%.4f,%.4f\n" % (
            track_id, num_spots, track_duration, track_start, track_stop, displacement
        ))
        
        # Write spots in this track
        for spot in track_spots:
            spots_in_tracks_writer.write("%d,%d,%d,%.4f,%.4f,%.4f,%.4f\n" % (
                track_id,
                spot_to_id.get(spot, -1),
                int(spot.getFeature('FRAME')),
                spot.getDoublePosition(0),
                spot.getDoublePosition(1),
                spot.getFeature('QUALITY'),
                spot.getFeature('RADIUS')
            ))
    
    # Export edges
    edges = track_model.trackEdges(track_id)
    for edge in edges:
        source = track_model.getEdgeSource(edge)
        target = track_model.getEdgeTarget(edge)
        
        source_id = spot_to_id.get(source, -1)
        target_id = spot_to_id.get(target, -1)
        
        dx = target.getDoublePosition(0) - source.getDoublePosition(0)
        dy = target.getDoublePosition(1) - source.getDoublePosition(1)
        disp = (dx**2 + dy**2)**0.5
        
        dt = (target.getFeature('FRAME') - source.getFeature('FRAME')) * time_interval
        velocity = disp / dt if dt > 0 else 0
        
        edges_writer.write("%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n" % (
            track_id, source_id, target_id, 0.0,
            target.getFeature('FRAME') * time_interval,
            target.getDoublePosition(0),
            target.getDoublePosition(1),
            velocity, disp
        ))

tracks_writer.close()
edges_writer.close()
spots_in_tracks_writer.close()

print "   Saved:", tracks_file.getAbsolutePath()
print "   Saved:", edges_file.getAbsolutePath()
print "   Saved:", spots_in_tracks_file.getAbsolutePath()

print "\n" + "=" * 60
print "TrackMate export completed successfully!"
print "=" * 60
