# OncoTrack UML Diagrams (Mermaid)

This document contains comprehensive UML diagrams for the oncoTrack repository using Mermaid syntax.

## Table of Contents
1. [Class Diagram](#1-class-diagram)
2. [Component Diagram](#2-component-diagram)
3. [Sequence Diagram - Region Selection](#3-sequence-diagram---region-selection)
4. [Sequence Diagram - Capture Flow](#4-sequence-diagram---capture-flow)
5. [State Machine Diagram](#5-state-machine-diagram)
6. [Use Case Diagram](#6-use-case-diagram)
7. [Architecture Overview](#7-architecture-overview)

---

## 1. Class Diagram

```mermaid
classDiagram
    class CaptureRegion {
        <<dataclass>>
        +int x
        +int y
        +int w
        +int h
    }

    class ScreenSelector {
        <<QWidget>>
        -QPoint _origin
        -QRubberBand _rubber
        -QRect _virtual
        +Signal selected
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
        -QLabel folder_label
        -QLabel region_label
        -QComboBox minutes_combo
        -QComboBox seconds_combo
        -QPushButton select_btn
        -QPushButton play_btn
        -QPushButton stop_btn
        -QPushButton open_btn
        -QLabel status
        -QPlainTextEdit log
        +__init__()
        +build_ui() void
        +log_msg(msg: str) void
        +update_ui() void
        +interval_ms() int
        +interval_label() str
        +select_area() void
        +on_selected(rect_local: QRect, overlay_top_left: QPoint) void
        +start_capture() void
        +stop_capture() void
        +open_folder() void
        +capture() void
    }

    class QWidget {
        <<Qt Framework>>
    }

    class QMainWindow {
        <<Qt Framework>>
    }

    class QTimer {
        <<Qt Framework>>
        +timeout Signal
        +start(ms: int) void
        +stop() void
        +isActive() bool
    }

    class QGuiApplication {
        <<Qt Framework>>
        +primaryScreen() QScreen
    }

    QWidget <|-- ScreenSelector
    QMainWindow <|-- ScreenshotApp
    ScreenshotApp o-- CaptureRegion : uses
    ScreenshotApp *-- ScreenSelector : creates
    ScreenshotApp *-- QTimer : contains
    ScreenshotApp ..> QGuiApplication : depends
    ScreenSelector ..> QGuiApplication : depends
```

---

## 2. Component Diagram

```mermaid
graph TB
    subgraph "OncoTrack Application"
        FC[FrameCapture Module<br/>frameCapture.py]
        subgraph "Components"
            SA[ScreenshotApp<br/>Main Controller]
            SS[ScreenSelector<br/>Region Selector]
            CR[CaptureRegion<br/>Data Model]
        end
    end
    
    subgraph "External Dependencies"
        QT[PySide6 Framework<br/>Qt GUI Library]
        PY[Python Standard Library<br/>sys, os, datetime, pathlib]
    end
    
    subgraph "File System"
        OUT[Output Directory<br/>~/Documents/OncoTrackSnaps/]
        FRAMES[PNG Frame Files<br/>frame_YYYYMMDD_HHMMSS_ffffff.png]
    end
    
    FC --> SA
    FC --> SS
    FC --> CR
    SA --> QT
    SS --> QT
    SA --> PY
    SA --> OUT
    OUT --> FRAMES
    
    style FC fill:#e1f5ff
    style SA fill:#fff4e1
    style SS fill:#fff4e1
    style CR fill:#fff4e1
    style QT fill:#ffe1f5
    style OUT fill:#e1ffe1
```

---

## 3. Sequence Diagram - Region Selection

```mermaid
sequenceDiagram
    actor User
    participant UI as ScreenshotApp
    participant Selector as ScreenSelector
    participant Display as Screen Overlay
    participant Data as CaptureRegion

    User->>UI: Click "Define ROI"
    UI->>UI: select_area()
    UI->>Selector: create instance
    UI->>Selector: start()
    Selector->>Display: show fullscreen overlay
    Selector->>Selector: grabMouse() & grabKeyboard()
    
    User->>Selector: mouse press (start drag)
    Selector->>Selector: mousePressEvent()
    Selector->>Selector: store origin point
    Selector->>Display: show rubber band
    
    User->>Selector: mouse move (drag)
    Selector->>Selector: mouseMoveEvent()
    Selector->>Display: update rubber band geometry
    
    User->>Selector: mouse release
    Selector->>Selector: mouseReleaseEvent()
    Selector->>Selector: validate size > 5px
    
    alt Valid Selection
        Selector->>UI: emit selected(rect, topLeft)
        Selector->>Selector: stop()
        Selector->>Display: close overlay
        UI->>UI: on_selected()
        UI->>Data: create CaptureRegion(x, y, w, h)
        Data-->>UI: region instance
        UI->>UI: update_ui()
        UI->>UI: log_msg("ROI set")
    else Invalid Selection (too small)
        Selector->>UI: emit cancelled()
        Selector->>Selector: stop()
        UI->>UI: log_msg("cancelled")
    end
    
    Note over User,Data: Alternative: User presses Escape
    User->>Selector: press Escape key
    Selector->>Selector: keyPressEvent()
    Selector->>UI: emit cancelled()
    Selector->>Selector: stop()
```

---

## 4. Sequence Diagram - Capture Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as ScreenshotApp
    participant Timer as QTimer
    participant Screen as QGuiApplication
    participant FS as File System

    User->>UI: Click "Start Capture"
    UI->>UI: start_capture()
    
    Note over UI: Immediate first capture
    UI->>UI: capture()
    UI->>Screen: primaryScreen()
    Screen-->>UI: screen object
    UI->>Screen: grabWindow(0, x, y, w, h)
    Screen-->>UI: pixmap
    UI->>UI: generate timestamp
    UI->>FS: save PNG to ~/Documents/OncoTrackSnaps/
    UI->>UI: log_msg("Saved frame_...")
    
    UI->>Timer: start(interval_ms)
    UI->>UI: update_ui()
    UI->>UI: log_msg("Capture started")
    
    loop Every interval (e.g., every 20 seconds)
        Timer->>UI: timeout signal
        UI->>UI: capture()
        UI->>Screen: primaryScreen()
        Screen-->>UI: screen object
        UI->>Screen: grabWindow(0, x, y, w, h)
        Screen-->>UI: pixmap
        UI->>UI: generate timestamp
        UI->>FS: save PNG to ~/Documents/OncoTrackSnaps/
        UI->>UI: log_msg("Saved frame_...")
    end
    
    Note over User,FS: Stop Capture
    User->>UI: Click "Stop Capture"
    UI->>UI: stop_capture()
    UI->>Timer: stop()
    UI->>UI: update_ui()
    UI->>UI: log_msg("Capture stopped")
```

---

## 5. State Machine Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle: Application Start
    
    Idle: No region defined
    Idle: Timer stopped
    Idle: Enable: Define ROI, Open Folder
    Idle: Disable: Start Capture, Stop Capture
    
    RegionSelecting: Fullscreen overlay active
    RegionSelecting: Mouse/Keyboard grabbed
    RegionSelecting: Drawing rubber band
    
    RegionDefined: Region stored (CaptureRegion)
    RegionDefined: Timer stopped
    RegionDefined: Enable: Define ROI, Start Capture, Open Folder
    RegionDefined: Disable: Stop Capture
    
    Capturing: Timer active
    Capturing: Periodic captures running
    Capturing: Enable: Stop Capture, Open Folder
    Capturing: Disable: Define ROI, Start Capture, Interval Controls
    
    Idle --> RegionSelecting: Click "Define ROI"
    RegionSelecting --> RegionDefined: Valid selection\n(width > 5 && height > 5)
    RegionSelecting --> Idle: Cancelled\n(Escape or invalid size)
    RegionDefined --> RegionSelecting: Click "Define ROI"\n(redefine region)
    RegionDefined --> Capturing: Click "Start Capture"\n(region exists && interval > 0)
    Capturing --> RegionDefined: Click "Stop Capture"
    
    note right of RegionDefined
        Region persists until
        redefined or app closes
    end note
    
    note right of Capturing
        Captures continue until
        explicitly stopped
    end note
```

---

## 6. Use Case Diagram

```mermaid
graph TB
    User((User))
    
    subgraph "OncoTrack Frame Capture System"
        UC1[Define Capture Region]
        UC2[Configure Capture Interval]
        UC3[Start Automatic Capture]
        UC4[Stop Automatic Capture]
        UC5[View Captured Frames]
        UC6[Monitor Capture Status]
        UC7[Select Minutes]
        UC8[Select Seconds]
    end
    
    User --> UC1
    User --> UC2
    User --> UC3
    User --> UC4
    User --> UC5
    User --> UC6
    
    UC2 --> UC7
    UC2 --> UC8
    
    UC3 -.->|requires| UC1
    UC3 -.->|requires| UC2
    UC4 -.->|requires| UC3
    
    style User fill:#ffcccc
    style UC1 fill:#cce5ff
    style UC2 fill:#cce5ff
    style UC3 fill:#ccffcc
    style UC4 fill:#ffcccc
    style UC5 fill:#ffff99
    style UC6 fill:#ffff99
```

---

## 7. Architecture Overview

```mermaid
graph TB
    subgraph "Presentation Layer"
        MW[Main Window<br/>ScreenshotApp]
        OV[Overlay<br/>ScreenSelector]
    end
    
    subgraph "Business Logic Layer"
        TM[Timer Management]
        SC[Screen Capture Logic]
        RC[Region Calculation]
    end
    
    subgraph "Data Layer"
        CR[CaptureRegion<br/>Immutable Data]
        CFG[Configuration<br/>Interval Settings]
    end
    
    subgraph "External Services"
        QT[Qt Framework<br/>GUI & Screen API]
        FS[File System<br/>PNG Storage]
    end
    
    MW --> TM
    MW --> SC
    MW --> OV
    MW --> CR
    MW --> CFG
    
    OV --> RC
    OV --> QT
    
    TM --> SC
    SC --> QT
    SC --> FS
    RC --> CR
    
    style MW fill:#ff9999
    style OV fill:#ff9999
    style TM fill:#99ccff
    style SC fill:#99ccff
    style RC fill:#99ccff
    style CR fill:#99ff99
    style CFG fill:#99ff99
    style QT fill:#ffcc99
    style FS fill:#ffcc99
```

---

## Design Patterns Used

```mermaid
mindmap
  root((Design Patterns<br/>in OncoTrack))
    Observer Pattern
      Qt Signals/Slots
      selected signal
      cancelled signal
      timeout signal
    Model-View Pattern
      CaptureRegion (Model)
      ScreenshotApp (View/Controller)
    Value Object
      CaptureRegion
      Immutable dataclass
      Frozen attributes
    Command Pattern
      Button click handlers
      select_area()
      start_capture()
      stop_capture()
    Template Method
      Qt event handlers
      paintEvent()
      mousePressEvent()
      keyPressEvent()
```

---

## Data Flow Diagram

```mermaid
flowchart LR
    A[User Input] --> B{Action Type?}
    
    B -->|Define ROI| C[ScreenSelector]
    C --> D[Mouse Drag]
    D --> E[Calculate Coordinates]
    E --> F[Create CaptureRegion]
    F --> G[Store in ScreenshotApp]
    
    B -->|Configure Interval| H[Update Combo Boxes]
    H --> I[Calculate Milliseconds]
    
    B -->|Start Capture| J[Validate Region & Interval]
    J --> K[Execute Immediate Capture]
    K --> L[Start QTimer]
    
    L --> M[Timer Timeout]
    M --> N[Capture Screen]
    N --> O[Generate Timestamp]
    O --> P[Save PNG File]
    P --> Q[Log Message]
    Q --> M
    
    B -->|Stop Capture| R[Stop QTimer]
    
    N --> S[QGuiApplication]
    S --> T[Primary Screen]
    T --> U[grabWindow with Region]
    U --> N
    
    P --> V[File System]
    V --> W[~/Documents/OncoTrackSnaps/]
    
    style A fill:#ffe6e6
    style F fill:#e6ffe6
    style P fill:#e6f3ff
    style W fill:#fff9e6
```

---

## Future Expansion - Proposed Architecture

```mermaid
graph TB
    subgraph "Current Implementation"
        FC[FrameCapture Module]
    end
    
    subgraph "Proposed Additional Modules"
        IA[Image Analysis Module]
        CT[Cell Tracking Module]
        DE[Data Export Module]
        PM[Project Management Module]
        VZ[Visualization Module]
    end
    
    subgraph "Proposed New Classes"
        IP[ImageProcessor]
        CellT[CellTracker]
        Exp[DataExporter]
        Proj[Project]
        Config[ConfigManager]
    end
    
    FC --> IA
    IA --> IP
    IA --> CT
    CT --> CellT
    IA --> DE
    DE --> Exp
    FC --> PM
    PM --> Proj
    PM --> Config
    CT --> VZ
    
    style FC fill:#90EE90
    style IA fill:#FFB6C1
    style CT fill:#87CEEB
    style DE fill:#DDA0DD
    style PM fill:#F0E68C
    style VZ fill:#FFA07A
```

---

## Notes

- All diagrams are in Mermaid syntax and can be rendered in:
  - GitHub (native support)
  - VS Code (with Mermaid extension)
  - Online editors like mermaid.live
  - Documentation sites (GitBook, Docusaurus, etc.)

- To view these diagrams:
  1. Install a Mermaid preview extension in your editor
  2. Or visit https://mermaid.live and paste the code blocks
  3. Or view this file in GitHub (it renders Mermaid automatically)

- These diagrams represent the current state of the codebase
- The "Future Expansion" section shows potential architectural growth
