# OncoTrack

A desktop application for capturing microscope frames and tracking cell movement over time. OncoTrack overlays live cell tracks on your screen, runs automated detection via Fiji/TrackMate, and exports position data for further analysis.

**Authors:**
- Sarah Thach — st13460@georgiasouthern.edu
- Sydney Boles — sb35329@georgiasouthern.edu
- Phillip Mejia — om00913@georgiasouthern.edu

---

## Getting Started

### Requirements

- Windows 10 or 11
- Fiji (ImageJ) with TrackMate — included in the provided zip

### Installation

1. Unzip `OncoTrack.zip` to any folder on your machine
2. The unzipped folder should look like this:

```
OncoTrack/
├── OncoTrack.exe
├── Fiji/
│   └── fiji-windows-x64.exe
├── _internal/
└── (captures/ and data/ are created automatically on first run)
```

3. Double-click `OncoTrack.exe` to launch

No Python installation or configuration required.

---

## Using the Application

### 1. Select a Capture Region

When the app opens, click **Select Region** and drag over the area of your screen showing the microscope feed. This defines the region that will be captured and tracked.

### 2. Calibrate (Optional)

Use the **Calibration** panel to set the scale of your image (e.g., microns per pixel) and axis orientation. This ensures exported coordinates are in real-world units.

### 3. Capture Frames

Click **Capture** to take a screenshot of the selected region. Frames are saved automatically to a `captures/` folder next to `OncoTrack.exe`. You can capture frames manually or set up continuous capture.

### 4. Run the Tracking Pipeline

Click **Run Pipeline** to analyze captured frames. The app will:

- Send frames to Fiji/TrackMate for cell detection
- Stitch detected tracks across frames into persistent cell identities
- Store results in a local database (`data/tracking.db`)

This runs in the background — the status bar will indicate when it completes.

### 5. View Tracks

Once the pipeline finishes, cell tracks are drawn as overlays directly on the capture region. Each cell is assigned a unique color. The fastest-moving track is highlighted in red.

Hovering over a track dot shows a tooltip with:
- Cell ID
- Step velocity (in your calibrated units per second, if calibrated)

Tracks update automatically after each pipeline run.

---

## Output Files

All output is saved next to `OncoTrack.exe`:

| Path | Contents |
|---|---|
| `captures/` | Captured frame images (PNG) |
| `data/tracking.db` | SQLite database with all cell positions and track data |
| `captures/latest_calibration.json` | Saved calibration settings |
| `captures/latest_session_config.json` | Saved session settings (region, axis convention, etc.) |

The database can be opened with any SQLite viewer (e.g., [DB Browser for SQLite](https://sqlitebrowser.org/)). Key tables:

- **cells** — one row per tracked cell
- **points** — x/y position of each cell per frame
- **track_step_velocities** — per-step velocity between frames
- **track_avg_velocities** — average velocity per cell

---

## Adjusting Tracking Parameters

If cells are not being detected correctly, tracking parameters can be tuned. Open `_internal/src/config.py` in a text editor and adjust:

```python
radius: float = 5.0          # Expected cell radius in pixels — increase for larger cells
threshold: float = 5.0       # Detection sensitivity — lower to detect more spots
linking_max_distance: float = 50.0   # Max distance a cell can move between frames
max_frame_gap: int = 2       # Max frames a cell can disappear and still be linked
```

Restart the application after saving changes.

---

## Troubleshooting

**App opens but pipeline does not run**
- Confirm `Fiji/fiji-windows-x64.exe` exists inside the `OncoTrack/` folder
- Check that at least one frame has been captured before running the pipeline

**No cells detected**
- Lower the `threshold` value in `config.py` (e.g., try `2.0`)
- Increase `radius` if your cells are larger than ~5 pixels

**Tracks look broken or fragmented**
- Increase `linking_max_distance` if cells move far between frames
- Increase `max_frame_gap` if cells occasionally disappear for a frame or two

**App crashes on launch**
- Ensure `OncoTrack.exe` is run from inside the `OncoTrack/` folder, not moved out on its own
