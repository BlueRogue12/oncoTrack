# OncoTrack UML Diagrams (Mermaid)

This document contains UML diagrams for the oncoTrack repository using Mermaid syntax.

## Table of Contents
1. [System Architecture Overview](#1-system-architecture-overview)
2. [Class Diagrams](#2-class-diagrams)
3. [Pipeline Sequence Diagram](#3-pipeline-sequence-diagram)

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "Frame Capture Tool"
        FC[frameCapture.py<br/>ScreenshotApp / ScreenSelector]
        FC_OUT[captures/<br/>PNG frames]
    end

    subgraph "Tracking Pipeline  src/"
        FI[FrameIngester<br/>frame_ingest.py]
        DB[(TrackingStore<br/>SQLite DB)]
        FR[FijiRunner<br/>fiji_runner.py]
        EXT[Fiji / TrackMate<br/>Headless]
        CSV[TrackMate CSVs<br/>spots, tracks, edges]
        TMP[TrackMateParser<br/>parse_trackmate_outputs.py]
        TS[TrackStitcher<br/>stitcher.py]
        EXP[DataExporter<br/>export.py]
        VIZ[TrackVisualizer<br/>visualize.py]
        ORCH[IncrementalTracker<br/>main.py]
    end

    subgraph "Outputs"
        MCSV[master_tracks.csv<br/>cells_summary.csv<br/>events.csv]
        PNG[tracks.png<br/>visualization]
    end

    FC --> FC_OUT
    FC_OUT --> FI
    FI --> DB
    FI --> FR
    FR --> EXT
    EXT --> CSV
    CSV --> TMP
    TMP --> TS
    TS --> DB
    DB --> EXP
    DB --> VIZ
    EXP --> MCSV
    VIZ --> PNG

    ORCH -.->|orchestrates| FI
    ORCH -.->|orchestrates| FR
    ORCH -.->|orchestrates| TMP
    ORCH -.->|orchestrates| TS
    ORCH -.->|orchestrates| EXP
    ORCH -.->|orchestrates| VIZ

    style FC fill:#e1f5ff
    style ORCH fill:#fff4e1
    style DB fill:#e1ffe1
    style EXT fill:#ffe1f5
    style MCSV fill:#f5ffe1
    style PNG fill:#f5ffe1
```

---

## 2. Class Diagrams

### 2a. Frame Capture Tool (tools/frameCapture.py)

```mermaid
classDiagram
    class CaptureRegion {
        <<dataclass>>
        +int x
        +int y
        +int w
        +int h
    }

    class ROIOverlay {
        <<QWidget>>
        -CaptureRegion _region
        +__init__()
        +set_region_global(rect: QRect) void
        +paintEvent(event) void
    }

    class ScreenSelector {
        <<QWidget>>
        -QPoint _origin
        -QRubberBand _rubber
        +Signal selected_global
        +Signal cancelled
        +__init__()
        +start() void
        +stop() void
        +paintEvent(event) void
        +keyPressEvent(event) void
        +mousePressEvent(event) void
        +mouseMoveEvent(event) void
        +mouseReleaseEvent(event) void
    }

    class ScreenshotApp {
        <<QMainWindow>>
        -Path output_dir
        -CaptureRegion region
        -QTimer timer
        -ScreenSelector _selector
        -ROIOverlay _roi_overlay
        -bool _roi_box_enabled
        +__init__()
        +build_ui() void
        +log_msg(msg: str) void
        +update_ui() void
        +interval_ms() int
        +select_area() void
        +on_selected_global(rect: QRect) void
        +start_capture() void
        +stop_capture() void
        +capture() void
        +toggle_roi_box() void
        +clear_roi() void
        +open_folder() void
    }

    QWidget <|-- ROIOverlay
    QWidget <|-- ScreenSelector
    QMainWindow <|-- ScreenshotApp
    ScreenshotApp o-- CaptureRegion : stores
    ScreenshotApp *-- ScreenSelector : creates
    ScreenshotApp *-- ROIOverlay : creates
```

### 2b. Tracking Pipeline (src/)

```mermaid
classDiagram
    class TrackerConfig {
        <<dataclass>>
        +str fiji_path
        +Path fiji_script
        +int overlap_window
        +int min_overlap_points
        +float max_distance_gate
        +str detector_type
        +float radius
        +float threshold
        +float linking_max_distance
        +float gap_closing_max_distance
        +int max_frame_gap
        +float pixel_size
        +float time_interval
        +Path db_path
    }

    class TrackingStore {
        -Path db_path
        +get_connection() contextmanager
        +add_frame(frame_index, timestamp, source_path) void
        +get_max_frame_index() int
        +create_cell(first_frame) int
        +update_cell_last_frame(cell_id, last_frame) void
        +get_all_cells() list
        +add_points(points) void
        +get_cell_points(cell_id) list
        +get_points_in_frame_range(start, end) list
        +get_cells_in_frame_range(start, end) list
        +add_event(event_type, parent_id, child_id, frame) void
        +start_run(batch_id, params, ...) int
        +complete_run(run_id, xml_path, csv_paths) void
        +get_finalized_frame() int
        +set_finalized_frame(frame) void
    }

    class FrameIngester {
        <<static>>
        +discover_frames(batch_dir) list
        +assign_sequential_indices(frames, start) list
        +get_frame_range(frames) tuple
        +validate_frames(frames) void
        +infer_batch_name(batch_dir) str
    }

    class BatchManager {
        -Path batches_dir
        +list_batches() list
        +get_batch_path(batch_name) Path
        +load_batch_frames(batch_name) list
    }

    class FijiRunner {
        -TrackerConfig config
        +__init__(config)
        +run_trackmate_on_frames(frames_dir, output_dir) dict
        +run_on_tail_window(all_frames_dir, frame_indices, output_dir) dict
    }

    class Spot {
        <<dataclass>>
        +int spot_id
        +int frame
        +float x
        +float y
        +float quality
        +float radius
        +distance_to(other: Spot) float
    }

    class Track {
        <<dataclass>>
        +int track_id
        +list spots
        +int num_spots
        +float duration
        +float displacement
        +get_frames() list
        +get_spot_at_frame(frame) Spot
        +get_spots_in_frame_range(start, end) list
    }

    class TrackMateParser {
        <<static>>
        +parse_spots_csv(csv_path) dict
        +parse_spots_in_tracks_csv(csv_path) dict
        +parse_tracks_csv(csv_path) dict
        +parse_all(output_dir) dict
        +get_frame_range(tracks) tuple
        +get_tracks_in_frame_range(tracks, start, end) dict
    }

    class StitchingResult {
        <<dataclass>>
        +dict matched_cells
        +list new_cells
        +list division_events
        +int total_tracks
        +int total_points_added
    }

    class TrackStitcher {
        -TrackingStore store
        -int min_overlap_points
        -float max_distance_gate
        +__init__(store, min_overlap_points, max_distance_gate)
        +stitch_tracks(tracks, overlap_start, overlap_end, new_start) StitchingResult
        -_get_existing_cells_in_overlap(start, end) dict
        -_match_tracks_to_cells(tracks, cells, start, end) dict
        -_calculate_overlap_cost(cell_map, track_spots) float
        -_add_new_points(tracks, track_to_cell, new_frame_start) int
    }

    class DataExporter {
        -TrackingStore store
        +export_master_csv(output_path, cell_ids) void
        +export_cells_summary(output_path) void
        +export_events(output_path) void
    }

    class TrackVisualizer {
        -TrackingStore store
        -TrackerConfig config
        +render_all_tracks(output_path, canvas_size, background_image) void
        +render_specific_cells(cell_ids, output_path, ...) void
        -_draw_cell_track(canvas, cell_id) void
        -_generate_color(cell_id) tuple
    }

    class IncrementalTracker {
        -TrackerConfig config
        -TrackingStore store
        -FijiRunner fiji_runner
        -TrackStitcher stitcher
        -DataExporter exporter
        -TrackVisualizer visualizer
        +__init__(config)
        +process_batch(batch_path, batch_name) void
        +export_data(output_dir) void
        +visualize(output_path, background_image) void
    }

    Track "1" *-- "many" Spot : contains
    TrackMateParser ..> Track : creates
    TrackMateParser ..> Spot : creates
    TrackStitcher *-- TrackingStore : uses
    TrackStitcher ..> StitchingResult : returns
    DataExporter *-- TrackingStore : uses
    TrackVisualizer *-- TrackingStore : uses
    TrackVisualizer *-- TrackerConfig : uses
    FijiRunner *-- TrackerConfig : uses
    IncrementalTracker *-- TrackerConfig : uses
    IncrementalTracker *-- TrackingStore : owns
    IncrementalTracker *-- FijiRunner : owns
    IncrementalTracker *-- TrackStitcher : owns
    IncrementalTracker *-- DataExporter : owns
    IncrementalTracker *-- TrackVisualizer : owns
```

---

## 3. Pipeline Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant ORC as IncrementalTracker
    participant FI as FrameIngester
    participant DB as TrackingStore
    participant FR as FijiRunner
    participant TM as Fiji/TrackMate
    participant TMP as TrackMateParser
    participant TS as TrackStitcher

    User->>ORC: process_batch(batch_path)

    Note over ORC,FI: Step 1 — Discover Frames
    ORC->>FI: discover_frames(batch_path)
    FI-->>ORC: frames[]

    Note over ORC,DB: Step 2 — Register Frames
    ORC->>DB: add_frame() × N
    ORC->>DB: get_finalized_frame()
    DB-->>ORC: finalized_frame (null if first batch)

    Note over ORC: Step 3 — Determine Tail Window
    ORC->>ORC: calc overlap_frame_start/end

    Note over ORC,TM: Step 4 — Run TrackMate
    ORC->>FR: run_trackmate_on_frames(batch_path, output_dir)
    FR->>TM: fiji --headless --run script
    TM-->>FR: spots.csv, tracks.csv, edges.csv
    FR-->>ORC: output_paths dict

    Note over ORC,TMP: Step 5 — Parse Outputs
    ORC->>TMP: parse_all(output_dir)
    TMP-->>ORC: tracks dict[id → Track]

    Note over ORC,TS: Step 6 — Stitch Tracks
    alt First batch
        ORC->>DB: create_cell() × N
        ORC->>DB: add_points(all_spots)
    else Subsequent batch
        ORC->>TS: stitch_tracks(tracks, overlap_start, overlap_end, new_start)
        TS->>DB: get_cells_in_frame_range(overlap)
        DB-->>TS: existing_cells[]
        TS->>TS: build cost matrix (mean Euclidean distance)
        TS->>TS: greedy assignment (sort by min cost)
        TS->>DB: create_cell() for unmatched tracks
        TS->>DB: add_points(new frames only)
        TS-->>ORC: StitchingResult
    end

    Note over ORC,DB: Step 7 — Update Finalized Frame
    ORC->>DB: set_finalized_frame(frame_end - overlap_window)

    ORC-->>User: batch complete
```

---

## Notes

- All diagrams are in Mermaid syntax and can be rendered in:
  - GitHub (native support)
  - VS Code (with Mermaid extension)
  - Online editors like mermaid.live

- To view these diagrams:
  1. Install a Mermaid preview extension in your editor
  2. Or visit https://mermaid.live and paste the code blocks
  3. Or view this file in GitHub (it renders Mermaid automatically)
