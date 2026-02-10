/**
 * TrackMate Headless Script for Incremental Cell Tracking
 * 
 * This Groovy script runs TrackMate in headless mode (no GUI) on a sequence of frames.
 * It is designed to process a "tail window" of frames for incremental tracking.
 * 
 * Arguments (passed as system properties via -D flags):
 *   - input_frames_dir: Directory containing image frames (PNG/TIF)
 *   - output_dir: Directory for output CSV and XML files
 *   - detector: Detector type (default: DOG_DETECTOR)
 *   - radius: Cell radius in pixels (default: 5.0)
 *   - threshold: Quality threshold (default: 5.0)
 *   - linking_max_distance: Max linking distance (default: 15.0)
 *   - gap_closing_max_distance: Max gap closing distance (default: 15.0)
 *   - max_frame_gap: Max frames to bridge (default: 2)
 *   - pixel_size: Pixel size in microns (default: 1.0)
 *   - time_interval: Time between frames in seconds (default: 1.0)
 *   - do_subpixel: Enable subpixel localization (default: true)
 *   - do_median: Enable median filter (default: false)
 */

import ij.IJ
import ij.ImagePlus
import ij.ImageStack
import fiji.plugin.trackmate.TrackMate
import fiji.plugin.trackmate.Model
import fiji.plugin.trackmate.Settings
import fiji.plugin.trackmate.detection.LogDetectorFactory
import fiji.plugin.trackmate.detection.DogDetectorFactory
import fiji.plugin.trackmate.tracking.jaqaman.SparseLAPTrackerFactory
import fiji.plugin.trackmate.io.TmXmlWriter
import fiji.plugin.trackmate.Logger
import fiji.plugin.trackmate.action.ExportTracksToXML
import fiji.plugin.trackmate.Spot
import fiji.plugin.trackmate.SpotCollection
import fiji.plugin.trackmate.action.ExportStatsToIJAction

import java.io.File
import java.io.FileWriter
import java.io.PrintWriter

// Parse command-line arguments
def getArg(String key, String defaultValue) {
    return System.getProperty(key, defaultValue)
}

def getArgDouble(String key, double defaultValue) {
    String val = System.getProperty(key)
    return val != null ? Double.parseDouble(val) : defaultValue
}

def getArgInt(String key, int defaultValue) {
    String val = System.getProperty(key)
    return val != null ? Integer.parseInt(val) : defaultValue
}

def getArgBoolean(String key, boolean defaultValue) {
    String val = System.getProperty(key)
    return val != null ? Boolean.parseBoolean(val) : defaultValue
}

// Required arguments
String inputDir = getArg("input_frames_dir", null)
String outputDir = getArg("output_dir", null)

if (inputDir == null || outputDir == null) {
    println "ERROR: Missing required arguments"
    println "Usage: fiji --headless --run run_trackmate_tail.groovy '-Dinput_frames_dir=<path> -Doutput_dir=<path> [options]'"
    System.exit(1)
}

// Optional parameters
String detectorType = getArg("detector", "DOG_DETECTOR")
double radius = getArgDouble("radius", 5.0)
double threshold = getArgDouble("threshold", 5.0)
double linkingMaxDist = getArgDouble("linking_max_distance", 15.0)
double gapClosingMaxDist = getArgDouble("gap_closing_max_distance", 15.0)
int maxFrameGap = getArgInt("max_frame_gap", 2)
double pixelSize = getArgDouble("pixel_size", 1.0)
double timeInterval = getArgDouble("time_interval", 1.0)
boolean doSubpixel = getArgBoolean("do_subpixel", true)
boolean doMedian = getArgBoolean("do_median", false)
int targetChannel = getArgInt("target_channel", 1)

println "=== TrackMate Headless Tracking ==="
println "Input: $inputDir"
println "Output: $outputDir"
println "Detector: $detectorType, radius=$radius, threshold=$threshold"
println "Linking: max_dist=$linkingMaxDist, gap_closing=$gapClosingMaxDist, max_gap=$maxFrameGap"

// Create output directory
new File(outputDir).mkdirs()

// Load image stack from directory
println "Loading frames from $inputDir..."
File dir = new File(inputDir)
File[] files = dir.listFiles({ f -> 
    f.name.toLowerCase().endsWith(".png") || 
    f.name.toLowerCase().endsWith(".tif") || 
    f.name.toLowerCase().endsWith(".tiff")
} as FileFilter)

if (files == null || files.length == 0) {
    println "ERROR: No image files found in $inputDir"
    System.exit(1)
}

// Sort files by name
files = files.sort { it.name }
println "Found ${files.length} frames"

// Build image stack
ImagePlus firstImage = IJ.openImage(files[0].absolutePath)
if (firstImage == null) {
    println "ERROR: Failed to load first image: ${files[0].absolutePath}"
    System.exit(1)
}

ImageStack stack = new ImageStack(firstImage.width, firstImage.height)
for (File file : files) {
    ImagePlus img = IJ.openImage(file.absolutePath)
    if (img != null) {
        stack.addSlice(file.name, img.getProcessor())
    } else {
        println "WARNING: Failed to load ${file.name}"
    }
}

ImagePlus imp = new ImagePlus("Stack", stack)
println "Built stack: ${stack.size()} frames, ${imp.width}x${imp.height}"

// Configure TrackMate
Model model = new Model()
model.setLogger(Logger.IJ_LOGGER)

Settings settings = new Settings(imp)

// Set calibration
settings.dx = pixelSize
settings.dy = pixelSize
settings.dz = 1.0
settings.dt = timeInterval
settings.xstart = 0
settings.xend = imp.width
settings.ystart = 0
settings.yend = imp.height
settings.zstart = 0
settings.zend = imp.getNSlices() - 1
settings.tstart = 0
settings.tend = imp.getNFrames() - 1

// Configure detector
def detectorFactory
if (detectorType == "LOG_DETECTOR") {
    detectorFactory = new LogDetectorFactory()
} else {
    detectorFactory = new DogDetectorFactory()  // Default to DOG
}

settings.detectorFactory = detectorFactory
settings.detectorSettings = [
    'RADIUS': radius,
    'THRESHOLD': threshold,
    'DO_SUBPIXEL_LOCALIZATION': doSubpixel,
    'DO_MEDIAN_FILTERING': doMedian,
    'TARGET_CHANNEL': targetChannel
]

println "Detector configured: $detectorFactory"

// Configure tracker (LAP tracker)
settings.trackerFactory = new SparseLAPTrackerFactory()
settings.trackerSettings = [
    'LINKING_MAX_DISTANCE': linkingMaxDist,
    'GAP_CLOSING_MAX_DISTANCE': gapClosingMaxDist,
    'MAX_FRAME_GAP': maxFrameGap,
    'ALLOW_GAP_CLOSING': true,
    'ALLOW_TRACK_SPLITTING': true,
    'ALLOW_TRACK_MERGING': false,
    'SPLITTING_MAX_DISTANCE': linkingMaxDist,
    'ALTERNATIVE_LINKING_COST_FACTOR': 1.05,
    'CUTOFF_PERCENTILE': 0.9
]

println "Tracker configured: LAP with linking=$linkingMaxDist, gap_closing=$gapClosingMaxDist"

// Run TrackMate
println "Running detection..."
TrackMate trackmate = new TrackMate(model, settings)

boolean ok = trackmate.checkInput()
if (!ok) {
    println "ERROR: TrackMate configuration check failed: ${trackmate.getErrorMessage()}"
    System.exit(1)
}

ok = trackmate.process()
if (!ok) {
    println "ERROR: TrackMate processing failed: ${trackmate.getErrorMessage()}"
    System.exit(1)
}

println "TrackMate processing completed successfully"
println "Detected ${model.getSpots().getNSpots(false)} spots"
println "Found ${model.getTrackModel().nTracks(false)} tracks"

// Export TrackMate XML
println "Exporting TrackMate XML..."
File xmlFile = new File(outputDir, "trackmate.xml")
TmXmlWriter writer = new TmXmlWriter(xmlFile)
writer.appendModel(model)
writer.appendSettings(settings)
writer.writeToFile()
println "Saved: ${xmlFile.absolutePath}"

// Export spots CSV
println "Exporting spots.csv..."
File spotsFile = new File(outputDir, "spots.csv")
PrintWriter spotsWriter = new PrintWriter(new FileWriter(spotsFile))
spotsWriter.println("SPOT_ID,FRAME,POSITION_X,POSITION_Y,QUALITY,RADIUS")

SpotCollection spots = model.getSpots()
int spotCounter = 0
for (int frame = 0; frame < imp.getNFrames(); frame++) {
    def spotsInFrame = spots.iterable(frame, false)
    for (Spot spot : spotsInFrame) {
        spotsWriter.println(String.format("%d,%d,%.4f,%.4f,%.4f,%.4f",
            spotCounter++,
            frame,
            spot.getDoublePosition(0),
            spot.getDoublePosition(1),
            spot.getFeature(Spot.QUALITY),
            spot.getFeature(Spot.RADIUS)
        ))
    }
}
spotsWriter.close()
println "Saved: ${spotsFile.absolutePath}"

// Export tracks CSV
println "Exporting tracks.csv and edges.csv..."
File tracksFile = new File(outputDir, "tracks.csv")
File edgesFile = new File(outputDir, "edges.csv")
File spotsInTracksFile = new File(outputDir, "spots_in_tracks.csv")

PrintWriter tracksWriter = new PrintWriter(new FileWriter(tracksFile))
PrintWriter edgesWriter = new PrintWriter(new FileWriter(edgesFile))
PrintWriter spotsInTracksWriter = new PrintWriter(new FileWriter(spotsInTracksFile))

tracksWriter.println("TRACK_ID,NUMBER_SPOTS,NUMBER_GAPS,NUMBER_SPLITS,NUMBER_MERGES,NUMBER_COMPLEX,LONGEST_GAP,TRACK_DURATION,TRACK_START,TRACK_STOP,TRACK_DISPLACEMENT")
edgesWriter.println("TRACK_ID,SPOT_SOURCE_ID,SPOT_TARGET_ID,LINK_COST,EDGE_TIME,EDGE_X_LOCATION,EDGE_Y_LOCATION,VELOCITY,DISPLACEMENT")
spotsInTracksWriter.println("TRACK_ID,SPOT_ID,FRAME,POSITION_X,POSITION_Y,QUALITY,RADIUS")

def trackModel = model.getTrackModel()
def trackIDs = trackModel.trackIDs(false)

// Build spot-to-id mapping
Map<Spot, Integer> spotToID = new HashMap<>()
spotCounter = 0
for (int frame = 0; frame < imp.getNFrames(); frame++) {
    def spotsInFrame = spots.iterable(frame, false)
    for (Spot spot : spotsInFrame) {
        spotToID.put(spot, spotCounter++)
    }
}

trackIDs.eachWithIndex { trackID, idx ->
    def trackSpots = trackModel.trackSpots(trackID)
    def sortedSpots = trackSpots.toSorted { a, b -> 
        a.getFeature(Spot.FRAME).compareTo(b.getFeature(Spot.FRAME)) 
    }
    
    int numSpots = sortedSpots.size()
    int numGaps = 0
    int numSplits = trackModel.trackSplitPoints(trackID).size()
    int numMerges = trackModel.trackMergePoints(trackID).size()
    
    double trackStart = sortedSpots[0].getFeature(Spot.FRAME) * timeInterval
    double trackStop = sortedSpots[-1].getFeature(Spot.FRAME) * timeInterval
    double trackDuration = trackStop - trackStart
    
    double x0 = sortedSpots[0].getDoublePosition(0)
    double y0 = sortedSpots[0].getDoublePosition(1)
    double xN = sortedSpots[-1].getDoublePosition(0)
    double yN = sortedSpots[-1].getDoublePosition(1)
    double displacement = Math.sqrt((xN - x0) * (xN - x0) + (yN - y0) * (yN - y0))
    
    tracksWriter.println(String.format("%d,%d,%d,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f",
        trackID, numSpots, numGaps, numSplits, numMerges, 0, 0,
        trackDuration, trackStart, trackStop, displacement
    ))
    
    // Export spots in this track
    for (Spot spot : sortedSpots) {
        int spotID = spotToID.get(spot)
        spotsInTracksWriter.println(String.format("%d,%d,%d,%.4f,%.4f,%.4f,%.4f",
            trackID,
            spotID,
            (int) spot.getFeature(Spot.FRAME),
            spot.getDoublePosition(0),
            spot.getDoublePosition(1),
            spot.getFeature(Spot.QUALITY),
            spot.getFeature(Spot.RADIUS)
        ))
    }
    
    // Export edges
    def edges = trackModel.trackEdges(trackID)
    for (edge in edges) {
        Spot source = trackModel.getEdgeSource(edge)
        Spot target = trackModel.getEdgeTarget(edge)
        
        int sourceID = spotToID.get(source)
        int targetID = spotToID.get(target)
        
        double dx = target.getDoublePosition(0) - source.getDoublePosition(0)
        double dy = target.getDoublePosition(1) - source.getDoublePosition(1)
        double disp = Math.sqrt(dx * dx + dy * dy)
        double dt = (target.getFeature(Spot.FRAME) - source.getFeature(Spot.FRAME)) * timeInterval
        double velocity = dt > 0 ? disp / dt : 0
        
        edgesWriter.println(String.format("%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f",
            trackID, sourceID, targetID, 0.0,
            target.getFeature(Spot.FRAME) * timeInterval,
            target.getDoublePosition(0),
            target.getDoublePosition(1),
            velocity, disp
        ))
    }
}

tracksWriter.close()
edgesWriter.close()
spotsInTracksWriter.close()

println "Saved: ${tracksFile.absolutePath}"
println "Saved: ${edgesFile.absolutePath}"
println "Saved: ${spotsInTracksFile.absolutePath}"

println "=== TrackMate export completed successfully ==="
System.exit(0)
