import sys
import os
import json
import math
import sqlite3
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QRect, QPoint, QTimer, Signal, QThread
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QPushButton,
    QLabel,
    QComboBox,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QMessageBox,
    QCheckBox,
    QToolTip,
    QDialog,
    QSplitter,
    QSizePolicy,
    QFrame,
)

from src.capture_controller import CaptureController
from src.frame_capture_models import (
    CaptureRegion,
    Calibration,
    OriginConfig,
    AxisConvention,
    get_project_root,
    get_output_folder,
    get_latest_calibration_path,
    get_latest_session_config_path,
)
from src.frame_capture_overlays import (
    CalibrationDialog,
    ROIOverlay,
    CalibrationOverlay,
    OriginPickerOverlay,
    ScreenSelector,
)


# ----------------------------
# Track Overlay (cell tracks from database)
# ----------------------------

class TrackOverlay(QWidget):
    """Transparent overlay that draws cell track dots and connecting lines from the DB."""

    DOT_RADIUS = 2
    RING_RADIUS = 7

    _PALETTE = [
        (50, 180, 50),
        (50, 120, 220),
        (220, 160, 0),
        (180, 50, 220),
        (0, 200, 200),
        (220, 110, 0),
        (220, 50, 150),
        (100, 220, 80),
        (80, 180, 220),
        (160, 100, 220),
    ]
    _RED = (220, 50, 50)
    _HOVER_RADIUS_SQ = 8 * 8

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._points_by_cell: Dict[int, List[Tuple[float, float, float]]] = {}
        self._frame_w: int = 0
        self._frame_h: int = 0
        self._dpr: float = 1.0
        self._cell_color_index: Dict[int, int] = {}
        self._next_color_index: int = 0
        self._fastest_cell_id: Optional[int] = None

        self._hover_dots: List[Tuple[int, int, int, Optional[float]]] = []
        self._current_hover: Optional[Tuple[int, Optional[float]]] = None

        self._units_per_pixel: float = 1.0
        self._unit_name: str = "px"
        self._cursor_overridden: bool = False

        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(50)
        self._hover_timer.timeout.connect(self._check_hover)

    def _color_for_cell(self, cell_id: int) -> Tuple[int, int, int]:
        if cell_id == self._fastest_cell_id:
            return self._RED
        if cell_id not in self._cell_color_index:
            self._cell_color_index[cell_id] = self._next_color_index % len(self._PALETTE)
            self._next_color_index += 1
        return self._PALETTE[self._cell_color_index[cell_id]]

    def set_region_global(self, region: CaptureRegion):
        self.setGeometry(region.x, region.y, region.w, region.h)
        self._rebuild_hover_data()
        self.update()

    def set_tracks(
        self,
        points_by_cell: Dict[int, List[Tuple[float, float, float]]],
        fastest_cell_id: Optional[int] = None,
        frame_size: Optional[Tuple[int, int]] = None,
    ):
        self._points_by_cell = points_by_cell
        self._fastest_cell_id = fastest_cell_id
        if frame_size and frame_size[0] > 0 and frame_size[1] > 0:
            self._frame_w, self._frame_h = frame_size
        else:
            self._frame_w = 0
            self._frame_h = 0
        self._rebuild_hover_data()
        self.update()

    def set_dpr(self, dpr: float):
        self._dpr = max(0.01, float(dpr))
        self._rebuild_hover_data()
        self.update()

    def set_display_scale(self, units_per_pixel: float, unit_name: str):
        self._units_per_pixel = max(1e-12, float(units_per_pixel))
        self._unit_name = unit_name or "px"
        self._rebuild_hover_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._hover_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._hover_timer.stop()
        QToolTip.hideText()
        self._current_hover = None
        if self._cursor_overridden:
            QApplication.restoreOverrideCursor()
            self._cursor_overridden = False

    def _scale_xy(self, x: float, y: float) -> Tuple[int, int]:
        if self._frame_w > 0 and self._frame_h > 0:
            cx = int(round(x * self.width() / self._frame_w))
            cy = int(round(y * self.height() / self._frame_h))
        else:
            cx = int(round(x / self._dpr))
            cy = int(round(y / self._dpr))
        return cx, cy

    def _rebuild_hover_data(self):
        dots: List[Tuple[int, int, int, Optional[float]]] = []
        for cell_id, pts in self._points_by_cell.items():
            for i, pt in enumerate(pts):
                cx, cy = self._scale_xy(pt[0], pt[1])
                if i == 0:
                    vel_display = None
                else:
                    vel_raw = compute_step_velocity(pts[i - 1], pts[i])
                    vel_display = vel_raw * self._units_per_pixel if vel_raw is not None else None
                dots.append((cx, cy, cell_id, vel_display))
        self._hover_dots = dots

    def _check_hover(self):
        global_pos = QCursor.pos()
        geo = self.geometry()
        if not geo.contains(global_pos):
            if self._current_hover is not None:
                QToolTip.hideText()
                self._current_hover = None
            if self._cursor_overridden:
                QApplication.restoreOverrideCursor()
                self._cursor_overridden = False
            return

        local_x = global_pos.x() - geo.x()
        local_y = global_pos.y() - geo.y()

        hit: Optional[Tuple[int, Optional[float]]] = None
        for cx, cy, cell_id, vel in self._hover_dots:
            if (local_x - cx) ** 2 + (local_y - cy) ** 2 <= self._HOVER_RADIUS_SQ:
                hit = (cell_id, vel)
                break

        if hit == self._current_hover:
            return

        self._current_hover = hit
        if hit is not None:
            if not self._cursor_overridden:
                QApplication.setOverrideCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                self._cursor_overridden = True
            cell_id, vel = hit
            if vel is None:
                tip = f"Cell {cell_id}\nStep velocity: — (start of track)"
            else:
                tip = f"Cell {cell_id}\nStep velocity: {vel:.3f} {self._unit_name}/s"
            QToolTip.showText(global_pos, tip)
        else:
            if self._cursor_overridden:
                QApplication.restoreOverrideCursor()
                self._cursor_overridden = False
            QToolTip.hideText()

    def paintEvent(self, _event):
        if not self._points_by_cell:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for cell_id, pts in self._points_by_cell.items():
            r, g, b = self._color_for_cell(cell_id)
            line_color = QColor(r, g, b, 150)
            dot_color = QColor(r, g, b, 220)
            ring_color = QColor(r, g, b, 200)

            if len(pts) >= 2:
                line_pen = QPen(line_color)
                line_pen.setWidth(1)
                painter.setPen(line_pen)
                for i in range(len(pts) - 1):
                    x1, y1 = self._scale_xy(pts[i][0], pts[i][1])
                    x2, y2 = self._scale_xy(pts[i + 1][0], pts[i + 1][1])
                    painter.drawLine(QPoint(x1, y1), QPoint(x2, y2))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot_color)
            for pt in pts:
                cx, cy = self._scale_xy(pt[0], pt[1])
                painter.drawEllipse(QPoint(cx, cy), self.DOT_RADIUS, self.DOT_RADIUS)

            if pts:
                ring_pen = QPen(ring_color)
                ring_pen.setWidth(1)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                cx, cy = self._scale_xy(pts[-1][0], pts[-1][1])
                painter.drawEllipse(QPoint(cx, cy), self.RING_RADIUS, self.RING_RADIUS)


# ----------------------------
# Pipeline Worker (background thread)
# ----------------------------

class PipelineWorker(QThread):
    """Runs IncrementalTracker.process_batch() in a background thread."""

    finished = Signal(bool, str)

    def __init__(self, batch_path: Path,
            threshold=None,
            radius=None,
            linking=None,
            gap=None,
            frame_gap=None,
            subpixel=None,
            median=None):

        super().__init__()
        self._batch_path = batch_path

        self._threshold = threshold
        self._radius = radius
        self._linking = linking
        self._gap = gap
        self._frame_gap = frame_gap
        self._subpixel = subpixel
        self._median = median

    def run(self):
        try:
            project_root = get_project_root()
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from src.main import IncrementalTracker  # type: ignore
            from src.config import get_default_config  # type: ignore

            config = get_default_config()

            if self._threshold is not None:
                config.threshold = self._threshold

            if self._radius is not None:
                config.radius = self._radius

            if self._linking is not None:
                config.linking_max_distance = self._linking

            if self._gap is not None:
                config.gap_closing_max_distance = self._gap

            if self._frame_gap is not None:
                config.max_frame_gap = self._frame_gap

            config.do_subpixel = self._subpixel
            config.do_median_filter = self._median

            tracker = IncrementalTracker(config)
            tracker.process_batch(self._batch_path)
            self.finished.emit(True, "Pipeline completed successfully.")
        except Exception as exc:
            self.finished.emit(False, f"Pipeline error: {exc}")


# ----------------------------
# Main app
# ----------------------------

class ScreenshotApp(QMainWindow):
    ORIGIN_OPTIONS = [
        "Top-Left",
        "Top-Right",
        "Bottom-Left",
        "Bottom-Right",
        "Center",
        "Custom (click in ROI)",
    ]
    AXIS_SOURCE_OPTIONS = ["horizontal", "vertical"]

    def __init__(self):
        super().__init__()

        self.setWindowTitle("OncoTrack: Frame Capture")
        self.resize(860,620)

        self.output_dir = get_output_folder()
        self.region: Optional[CaptureRegion] = None

        self.capture_controller = CaptureController()
        self.capture_controller.on_frame_saved = self._on_frame_saved
        self.capture_controller.on_capture_error = self.log_msg
        self.capture_controller.before_capture_hook = self._before_capture_hook
        self.capture_controller.after_capture_hook = self._after_capture_hook

        self._selector: Optional[ScreenSelector] = None
        self._roi_overlay: Optional[ROIOverlay] = None
        self._roi_box_enabled: bool = True

        self._track_overlay: Optional[TrackOverlay] = None
        self._tracks_visible: bool = False

        self._db_path: Path = get_project_root() / "data" / "tracking.db"
        self._pipeline_timer: QTimer = QTimer(self)
        self._pipeline_timer.timeout.connect(self._run_pipeline_now)
        self._pipeline_worker: Optional[PipelineWorker] = None
        self._test_mode: bool = False

        self.calibration: Calibration = Calibration(units_per_pixel=1.0, unit_name="px")
        self._cal_overlay: Optional[CalibrationOverlay] = None

        self.origin: OriginConfig = OriginConfig(x_norm=1.0, y_norm=0.0, mode_name="Top-Right")
        self._origin_overlay: Optional[OriginPickerOverlay] = None

        self.axis_conv: AxisConvention = AxisConvention(
            x_axis_source="vertical",
            x_positive="down",
            y_axis_source="horizontal",
            y_positive="left",
        )
        self.main_splitter: Optional[QSplitter] = None
        self.control_panel: Optional[QWidget] = None
        self.visualization_panel: Optional[QWidget] = None
        self.setup_section: Optional[QWidget] = None
        self.run_section: Optional[QWidget] = None
        self.status_section: Optional[QWidget] = None

        self.build_ui()
        self.update_ui()
        self._write_session_config_json()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        root_layout.addWidget(self.main_splitter)

        # ----------------------------
        # Control panel
        # ----------------------------
        self.control_panel = QWidget()
        self.control_panel.setMinimumWidth(420)
        control_layout = QVBoxLayout(self.control_panel)
        control_layout.setContentsMargins(6, 6, 6, 6)
        control_layout.setSpacing(8)

        # Top controls section
        top_section, top_body = self._make_section("Session")
        control_layout.addWidget(top_section)

        panel_row = QHBoxLayout()
        panel_row.addWidget(QLabel("Panel position:"))

        self.panel_position_combo = QComboBox()
        self.panel_position_combo.addItems(["Left", "Right", "Top", "Bottom"])
        self.panel_position_combo.setCurrentText("Right")
        self.panel_position_combo.currentTextChanged.connect(self.on_panel_position_changed)

        panel_row.addWidget(self.panel_position_combo)
        panel_row.addStretch()
        top_body.addLayout(panel_row)

        self.folder_label = QLabel(f"Save folder: {self.output_dir}")
        self.folder_label.setWordWrap(True)
        top_body.addWidget(self.folder_label)

        self.region_label = QLabel("ROI: (none)")
        self.region_label.setWordWrap(True)
        top_body.addWidget(self.region_label)

        summary_row = QHBoxLayout()
        self.origin_label = QLabel("Origin: Top-Right")
        self.axis_label = QLabel("Axes: X=vertical (+down), Y=horizontal (+left)")
        self.cal_label = QLabel("Scale: not set")

        self.origin_label.setWordWrap(True)
        self.axis_label.setWordWrap(True)
        self.cal_label.setWordWrap(True)

        summary_row.addWidget(self.origin_label, 1)
        summary_row.addWidget(self.axis_label, 1)
        summary_row.addWidget(self.cal_label, 1)
        top_body.addLayout(summary_row)

        # ----------------------------
        # Setup section
        # ----------------------------
        self.setup_section, setup_body = self._make_section("Setup")
        control_layout.addWidget(self.setup_section)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Capture interval:"))

        self.minutes_combo = QComboBox()
        self.seconds_combo = QComboBox()

        for m in range(0, 60):
            self.minutes_combo.addItem(f"{m:02d}", m)
        for s in range(0, 60):
            self.seconds_combo.addItem(f"{s:02d}", s)

        self.minutes_combo.setCurrentIndex(0)
        self.seconds_combo.setCurrentIndex(20)

        interval_row.addWidget(QLabel("min"))
        interval_row.addWidget(self.minutes_combo)
        interval_row.addWidget(QLabel("sec"))
        interval_row.addWidget(self.seconds_combo)
        interval_row.addStretch()
        setup_body.addLayout(interval_row)

        settings_row = QHBoxLayout()

        # --- Threshold ---
        self.threshold_input = QLineEdit()
        self.threshold_input.setPlaceholderText("Threshold")
        self.threshold_input.setFixedWidth(80)
        settings_row.addWidget(QLabel("Threshold:"))
        settings_row.addWidget(self.threshold_input)

        # --- Radius ---
        self.radius_input = QLineEdit()
        self.radius_input.setPlaceholderText("Radius")
        self.radius_input.setFixedWidth(80)
        settings_row.addWidget(QLabel("Radius:"))
        settings_row.addWidget(self.radius_input)

        # --- Subpixel ---
        self.subpixel_checkbox = QCheckBox("Subpixel")
        self.subpixel_checkbox.setChecked(True)
        settings_row.addWidget(self.subpixel_checkbox)

        # --- Median filter ---
        self.median_checkbox = QCheckBox("Median")
        self.median_checkbox.setChecked(False)
        settings_row.addWidget(self.median_checkbox)

        tracking_row = QHBoxLayout()

        self.linking_input = QLineEdit()
        self.linking_input.setPlaceholderText("Linking")
        self.linking_input.setFixedWidth(80)

        self.gap_input = QLineEdit()
        self.gap_input.setPlaceholderText("Gap")
        self.gap_input.setFixedWidth(80)

        self.frame_gap_input = QLineEdit()
        self.frame_gap_input.setPlaceholderText("FrameGap")
        self.frame_gap_input.setFixedWidth(80)

        tracking_row.addWidget(QLabel("Linking:"))
        tracking_row.addWidget(self.linking_input)

        tracking_row.addWidget(QLabel("Gap:"))
        tracking_row.addWidget(self.gap_input)

        tracking_row.addWidget(QLabel("Frame Gap:"))
        tracking_row.addWidget(self.frame_gap_input)

        tracking_row.addStretch()

        setup_body.addLayout(tracking_row)

        settings_row.addStretch()
        setup_body.addLayout(settings_row)

        settings_row.addStretch()

        setup_body.addLayout(settings_row)

        row1 = QHBoxLayout()
        self.select_btn = QPushButton("Define / Redefine ROI")

        self.origin_combo = QComboBox()
        for name in self.ORIGIN_OPTIONS:
            self.origin_combo.addItem(name, name)
        self.origin_combo.setCurrentText("Top-Right")
        self.origin_combo.currentIndexChanged.connect(self.on_origin_mode_changed)

        self.pick_origin_btn = QPushButton("Pick Origin")
        self.pick_origin_btn.clicked.connect(self.start_origin_picker)

        self.reset_origin_btn = QPushButton("Reset Origin")
        self.reset_origin_btn.clicked.connect(self.reset_origin_to_default)

        self.calibrate_btn = QPushButton("Calibrate Scale")
        self.clear_cal_btn = QPushButton("Clear Calibration")

        self.select_btn.clicked.connect(self.select_area)
        self.calibrate_btn.clicked.connect(self.start_calibration)
        self.clear_cal_btn.clicked.connect(self.clear_calibration)

        row1.addWidget(self.select_btn)
        row1.addWidget(QLabel("Origin:"))
        row1.addWidget(self.origin_combo)
        row1.addWidget(self.pick_origin_btn)
        row1.addWidget(self.reset_origin_btn)
        row1.addWidget(self.calibrate_btn)
        row1.addWidget(self.clear_cal_btn)
        row1.addStretch()
        setup_body.addLayout(row1)

        axis_title = QLabel("User axes:")
        axis_title.setStyleSheet("font-weight: 600;")
        setup_body.addWidget(axis_title)

        self.x_axis_source_combo = QComboBox()
        self.x_axis_source_combo.addItems(self.AXIS_SOURCE_OPTIONS)
        self.x_axis_source_combo.setCurrentText(self.axis_conv.x_axis_source)
        self.x_axis_source_combo.currentTextChanged.connect(self.on_axis_config_changed)

        self.x_axis_pos_combo = QComboBox()
        self.x_axis_pos_combo.currentTextChanged.connect(self.on_axis_config_changed)

        x_axis_row = QHBoxLayout()
        x_axis_row.addWidget(QLabel("X uses:"))
        x_axis_row.addWidget(self.x_axis_source_combo)
        x_axis_row.addWidget(QLabel("X positive:"))
        x_axis_row.addWidget(self.x_axis_pos_combo)
        x_axis_row.addStretch()
        setup_body.addLayout(x_axis_row)

        self.y_axis_source_combo = QComboBox()
        self.y_axis_source_combo.addItems(self.AXIS_SOURCE_OPTIONS)
        self.y_axis_source_combo.setCurrentText(self.axis_conv.y_axis_source)
        self.y_axis_source_combo.currentTextChanged.connect(self.on_axis_config_changed)

        self.y_axis_pos_combo = QComboBox()
        self.y_axis_pos_combo.currentTextChanged.connect(self.on_axis_config_changed)

        y_axis_row = QHBoxLayout()
        y_axis_row.addWidget(QLabel("Y uses:"))
        y_axis_row.addWidget(self.y_axis_source_combo)
        y_axis_row.addWidget(QLabel("Y positive:"))
        y_axis_row.addWidget(self.y_axis_pos_combo)
        y_axis_row.addStretch()
        setup_body.addLayout(y_axis_row)

        # ----------------------------
        # Run section
        # ----------------------------
        self.run_section, run_body = self._make_section("Run Controls")
        control_layout.addWidget(self.run_section)

        capture_row = QHBoxLayout()
        self.play_btn = QPushButton("Start Capture")
        self.stop_btn = QPushButton("Stop Capture")
        self.open_btn = QPushButton("Open Folder")
        self.clear_roi_btn = QPushButton("Clear ROI")

        self.roi_box_toggle_btn = QPushButton("ROI Box: ON")
        self.roi_box_toggle_btn.setCheckable(True)
        self.roi_box_toggle_btn.setChecked(True)
        self.roi_box_toggle_btn.clicked.connect(self.toggle_roi_box)

        self.play_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)
        self.open_btn.clicked.connect(self.open_folder)
        self.clear_roi_btn.clicked.connect(self.clear_roi)

        capture_row.addWidget(self.play_btn)
        capture_row.addWidget(self.stop_btn)
        capture_row.addWidget(self.open_btn)
        capture_row.addWidget(self.clear_roi_btn)
        capture_row.addWidget(self.roi_box_toggle_btn)
        capture_row.addStretch()
        run_body.addLayout(capture_row)

        pipeline_row = QHBoxLayout()
        pipeline_row.addWidget(QLabel("Pipeline interval:"))

        self.pipeline_minutes_combo = QComboBox()
        for m in range(1, 60):
            self.pipeline_minutes_combo.addItem(f"{m:02d}", m)
        self.pipeline_minutes_combo.setCurrentIndex(4)

        pipeline_row.addWidget(self.pipeline_minutes_combo)
        pipeline_row.addWidget(QLabel("min"))

        self.run_pipeline_btn = QPushButton("Run Pipeline Now")
        self.run_pipeline_btn.clicked.connect(self._run_pipeline_now)

        self.pipeline_auto_btn = QPushButton("Start Auto Pipeline")
        self.pipeline_auto_btn.setCheckable(True)
        self.pipeline_auto_btn.clicked.connect(self._toggle_auto_pipeline)

        self.test_mode_checkbox = QCheckBox("Test Mode")
        self.test_mode_checkbox.setChecked(False)
        self.test_mode_checkbox.toggled.connect(self._on_test_mode_toggled)

        pipeline_row.addWidget(self.run_pipeline_btn)
        pipeline_row.addWidget(self.pipeline_auto_btn)
        pipeline_row.addWidget(self.test_mode_checkbox)
        pipeline_row.addStretch()
        run_body.addLayout(pipeline_row)

        tracks_row = QHBoxLayout()
        self.tracks_toggle_btn = QPushButton("Tracks: OFF")
        self.tracks_toggle_btn.setCheckable(True)
        self.tracks_toggle_btn.setChecked(False)
        self.tracks_toggle_btn.clicked.connect(self._toggle_tracks)

        self.refresh_tracks_btn = QPushButton("Refresh Tracks")
        self.refresh_tracks_btn.clicked.connect(self._refresh_track_overlay)

        self.clear_tracks_btn = QPushButton("Clear Tracks")
        self.clear_tracks_btn.clicked.connect(self._clear_tracks)

        self.pipeline_status_label = QLabel("Pipeline: Idle")
        self.pipeline_status_label.setStyleSheet("font-weight: 600;")

        tracks_row.addWidget(self.tracks_toggle_btn)
        tracks_row.addWidget(self.refresh_tracks_btn)
        tracks_row.addWidget(self.clear_tracks_btn)
        tracks_row.addStretch()
        tracks_row.addWidget(self.pipeline_status_label)
        run_body.addLayout(tracks_row)

        # ----------------------------
        # Status / log
        # ----------------------------
        self.status_section, status_body = self._make_section("Status")
        control_layout.addWidget(self.status_section)

        self.status = QLabel("Capture status: Idle")
        self.status.setStyleSheet("font-weight: 600;")
        status_body.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        status_body.addWidget(self.log)

        control_layout.addStretch()

        # ----------------------------
        # Visualization panel
        # ----------------------------
        self.visualization_panel = QWidget()
        self.visualization_panel.setMinimumWidth(260)
        right_layout = QVBoxLayout(self.visualization_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(8)

        vis_section, vis_body = self._make_section("Visualization / Preview")
        right_layout.addWidget(vis_section)

        self.selected_cell_label = QLabel("Selected cell: none")
        vis_body.addWidget(self.selected_cell_label)

        self.track_summary_label = QLabel(
            "Track summary:\n"
            "- total tracks: --\n"
            "- fastest track: --\n"
            "- points loaded: --"
        )
        self.track_summary_label.setStyleSheet("padding: 6px; border: 1px solid #ccc; background: white;")
        vis_body.addWidget(self.track_summary_label)

        self.chart_placeholder = QPlainTextEdit()
        self.chart_placeholder.setReadOnly(True)
        self.chart_placeholder.setPlainText(
            "Insert data visualization here.\n\n"
            "Later this can hold:\n"
            "- velocity charts\n"
            "- displacement charts\n"
            "- per-cell summaries\n"
            "- selected-cell detail\n"
            "- tables / stats"
        )
        vis_body.addWidget(self.chart_placeholder)

        right_layout.addStretch()

        self.apply_panel_layout(self.panel_position_combo.currentText())
        self._refresh_axis_direction_choices()
        self._refresh_origin_display()
        self._refresh_axis_display()
        self._refresh_calibration_display()
        self._apply_mode_visibility()
    
    def _apply_mode_visibility(self):
        running = self.capture_controller.is_running()

        if self.setup_section is not None:
            self.setup_section.setVisible(not running)

        if self.visualization_panel is not None:
            self.visualization_panel.setVisible(running)

        if hasattr(self, "log"):
            self.log.setMaximumHeight(100 if running else 120)

        position = self.panel_position_combo.currentText()
        self.apply_panel_layout(position)
    
    def update_ui(self):
        running = self.capture_controller.is_running()
        custom_selected = self.origin_combo.currentText() == "Custom (click in ROI)"

        self.select_btn.setEnabled(not running)
        self.minutes_combo.setEnabled(not running)
        self.seconds_combo.setEnabled(not running)

        self.origin_combo.setEnabled((self.region is not None) and (not running))
        self.pick_origin_btn.setEnabled((self.region is not None) and (not running) and custom_selected)
        self.reset_origin_btn.setEnabled((self.region is not None) and (not running))

        self.calibrate_btn.setEnabled((self.region is not None) and (not running))
        self.clear_cal_btn.setEnabled((not running) and (self.calibration.unit_name != "px"))

        self.x_axis_source_combo.setEnabled((self.region is not None) and (not running))
        self.x_axis_pos_combo.setEnabled((self.region is not None) and (not running))
        self.y_axis_source_combo.setEnabled((self.region is not None) and (not running))
        self.y_axis_pos_combo.setEnabled((self.region is not None) and (not running))

        self.play_btn.setEnabled((self.region is not None) and (not running))
        self.stop_btn.setEnabled(running)

        self.clear_roi_btn.setEnabled((self.region is not None) and (not running))
        self.roi_box_toggle_btn.setEnabled(self.region is not None)

        self.status.setText("Capture status: Capturing" if running else "Capture status: Idle")
        self.roi_box_toggle_btn.setText("ROI Box: ON" if self._roi_box_enabled else "ROI Box: OFF")

        pipeline_busy = self._pipeline_worker is not None and self._pipeline_worker.isRunning()
        auto_pipeline_on = self._pipeline_timer.isActive()

        self.run_pipeline_btn.setEnabled(not pipeline_busy)
        self.pipeline_minutes_combo.setEnabled(not auto_pipeline_on and not pipeline_busy)
        self.pipeline_auto_btn.setText("Stop Auto Pipeline" if auto_pipeline_on else "Start Auto Pipeline")
        self.pipeline_auto_btn.setChecked(auto_pipeline_on)

        self.tracks_toggle_btn.setText("Tracks: ON" if self._tracks_visible else "Tracks: OFF")
        self.tracks_toggle_btn.setChecked(self._tracks_visible)
        self.refresh_tracks_btn.setEnabled(running and self.region is not None)
        self.clear_tracks_btn.setEnabled(running and self.region is not None)

        self._apply_mode_visibility()

    def log_msg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def _make_section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                border: 1px solid #cfcfcf;
                border-radius: 6px;
                background: #f7f7f7;
            }
        """)

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 700; border: none; background: transparent;")
        outer.addWidget(title_label)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)
        outer.addLayout(body)

        return frame, body
    
    def on_panel_position_changed(self, position: str):
        self.apply_panel_layout(position)

    def apply_panel_layout(self, position: str):
        if self.main_splitter is None or self.control_panel is None or self.visualization_panel is None:
            return

        self.control_panel.setParent(None)
        self.visualization_panel.setParent(None)

        if position == "Left":
            self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
            self.main_splitter.addWidget(self.control_panel)
            self.main_splitter.addWidget(self.visualization_panel)
            self.main_splitter.setSizes([520, 300])

        elif position == "Right":
            self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
            self.main_splitter.addWidget(self.visualization_panel)
            self.main_splitter.addWidget(self.control_panel)
            self.main_splitter.setSizes([300, 520])

        elif position == "Top":
            self.main_splitter.setOrientation(Qt.Orientation.Vertical)
            self.main_splitter.addWidget(self.control_panel)
            self.main_splitter.addWidget(self.visualization_panel)
            self.main_splitter.setSizes([420, 220])

        elif position == "Bottom":
            self.main_splitter.setOrientation(Qt.Orientation.Vertical)
            self.main_splitter.addWidget(self.visualization_panel)
            self.main_splitter.addWidget(self.control_panel)
            self.main_splitter.setSizes([220, 420])

    def _on_frame_saved(self, path: Path):
        self.log_msg(f"Saved {path.name}")

    def _before_capture_hook(self):
        overlay_was_visible = self._roi_overlay is not None and self._roi_overlay.isVisible()
        track_was_visible = self._track_overlay is not None and self._track_overlay.isVisible()

        self._overlay_was_visible_before_capture = overlay_was_visible
        self._track_was_visible_before_capture = track_was_visible

        if overlay_was_visible:
            self._hide_roi_overlay()
        if track_was_visible:
            self._hide_track_overlay()
        if overlay_was_visible or track_was_visible:
            QApplication.processEvents()

    def _after_capture_hook(self):
        if getattr(self, "_overlay_was_visible_before_capture", False):
            self._show_roi_overlay()
        if getattr(self, "_track_was_visible_before_capture", False):
            self._show_track_overlay()
        if getattr(self, "_overlay_was_visible_before_capture", False) or getattr(self, "_track_was_visible_before_capture", False):
            QApplication.processEvents()

    # ----------------------------
    # ROI overlay helpers
    # ----------------------------

    def _ensure_overlay(self):
        if self._roi_overlay is None:
            self._roi_overlay = ROIOverlay()

    def _show_roi_overlay(self):
        if not self._roi_box_enabled or self.region is None:
            return
        self._ensure_overlay()
        self._roi_overlay.set_region_global(self.region)
        self._roi_overlay.set_origin(self.origin)
        self._roi_overlay.set_show_origin_marker(not self.capture_controller.is_running())
        self._roi_overlay.show()
        self._roi_overlay.raise_()

    def _hide_roi_overlay(self):
        if self._roi_overlay is not None:
            self._roi_overlay.hide()

    def toggle_roi_box(self):
        self._roi_box_enabled = self.roi_box_toggle_btn.isChecked()
        if self._roi_box_enabled:
            self._show_roi_overlay()
            self.log_msg("ROI box shown.")
        else:
            self._hide_roi_overlay()
            self.log_msg("ROI box hidden.")
        self.update_ui()

    # ----------------------------
    # Track overlay helpers
    # ----------------------------

    def _get_roi_dpr(self) -> float:
        if self.region is None:
            return 1.0
        screen = QGuiApplication.screenAt(QPoint(self.region.x, self.region.y))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return float(screen.devicePixelRatio()) if screen else 1.0

    def _ensure_track_overlay(self):
        if self._track_overlay is None:
            self._track_overlay = TrackOverlay()

    def _show_track_overlay(self):
        if not self._tracks_visible or self.region is None:
            return
        self._ensure_track_overlay()
        self._track_overlay.set_region_global(self.region)
        self._track_overlay.set_dpr(self._get_roi_dpr())
        self._track_overlay.show()
        self._track_overlay.raise_()

    def _hide_track_overlay(self):
        if self._track_overlay is not None:
            self._track_overlay.hide()

    def _toggle_tracks(self):
        self._tracks_visible = self.tracks_toggle_btn.isChecked()
        if self._tracks_visible:
            self._show_track_overlay()
            self.log_msg("Track overlay shown.")
        else:
            self._hide_track_overlay()
            self.log_msg("Track overlay hidden.")
        self.update_ui()

    def _clear_tracks(self):
        if self._track_overlay is not None:
            self._track_overlay.set_tracks({})
        self.log_msg("Tracks cleared from overlay.")

    def _refresh_track_overlay(self):
        tracks, frame_size = load_tracks_from_db(self._db_path)
        if not tracks:
            self.log_msg(f"No tracks found in database ({self._db_path.name}).")
            if hasattr(self, "track_summary_label"):
                self.track_summary_label.setText(
                    "Track summary:\n"
                    "- total tracks: 0\n"
                    "- fastest track: --\n"
                    "- points loaded: 0"
                )
            return

        total_pts = sum(len(v) for v in tracks.values())
        fastest_id = compute_and_store_velocities(self._db_path)

        msg = f"Loaded {len(tracks)} cell track(s) ({total_pts} points) from DB."
        if fastest_id is not None:
            msg += f" Fastest track: cell {fastest_id} (shown in red)."
        self.log_msg(msg)

        if hasattr(self, "track_summary_label"):
            self.track_summary_label.setText(
                f"Track summary:\n"
                f"- total tracks: {len(tracks)}\n"
                f"- fastest track: {fastest_id if fastest_id is not None else '--'}\n"
                f"- points loaded: {total_pts}"
            )

        self._ensure_track_overlay()
        self._track_overlay.set_display_scale(
            self.calibration.units_per_pixel,
            self.calibration.unit_name,
        )
        self._track_overlay.set_tracks(tracks, fastest_cell_id=fastest_id, frame_size=frame_size)
        if self._tracks_visible and self.region is not None:
            self._show_track_overlay()

    # ----------------------------
    # Pipeline execution
    # ----------------------------

    def _on_test_mode_toggled(self, checked: bool):
        self._test_mode = checked
        state = "ON — pipeline will use vid1_frames/" if checked else "OFF — pipeline will use captures/"
        self.log_msg(f"Test mode {state}")

    def _run_pipeline_now(self):
        threshold = float(self.threshold_input.text()) if self.threshold_input.text() else None
        radius = float(self.radius_input.text()) if self.radius_input.text() else None
        linking = float(self.linking_input.text()) if self.linking_input.text() else None
        gap = float(self.gap_input.text()) if self.gap_input.text() else None
        frame_gap = int(self.frame_gap_input.text()) if self.frame_gap_input.text() else None

        subpixel = self.subpixel_checkbox.isChecked()
        median = self.median_checkbox.isChecked()

        if self._pipeline_worker is not None and self._pipeline_worker.isRunning():
            self.log_msg("Pipeline already running — skipping.")
            return
        batch_path = get_project_root() / "vid1_frames" if self._test_mode else get_output_folder()
        frame_exts = {".png", ".tif", ".tiff", ".jpg", ".jpeg"}
        has_frames = batch_path.exists() and any(f.suffix.lower() in frame_exts for f in batch_path.iterdir())
        if not has_frames:
            self.log_msg(
                f"No frames found in {batch_path}. "
                f"{'Check vid1_frames/ folder.' if self._test_mode else 'Capture some frames first.'}"
            )
            return
        self.log_msg(f"Starting pipeline on {batch_path} …")
        self.pipeline_status_label.setText("Pipeline: Running")
        self._pipeline_worker = PipelineWorker(
            batch_path,
            threshold=threshold,
            radius=radius,
            linking=linking,
            gap=gap,
            frame_gap=frame_gap,
            subpixel=subpixel,
            median=median
        )

        self._pipeline_worker.finished.connect(self._on_pipeline_finished)
        self._pipeline_worker.start()
        self.update_ui()

    def _on_pipeline_finished(self, success: bool, message: str):
        self.log_msg(message)
        self.pipeline_status_label.setText("Pipeline: Done" if success else "Pipeline: Error")
        self._pipeline_worker = None
        if success:
            self._refresh_track_overlay()
        self.update_ui()

    def _toggle_auto_pipeline(self):
        if self.pipeline_auto_btn.isChecked():
            minutes = int(self.pipeline_minutes_combo.currentData())
            self._pipeline_timer.start(minutes * 60 * 1000)
            self.log_msg(f"Auto pipeline started (every {minutes} min).")
        else:
            self._pipeline_timer.stop()
            self.log_msg("Auto pipeline stopped.")
        self.update_ui()

    # ----------------------------
    # ROI selection
    # ----------------------------

    def clear_roi(self):
        if self.capture_controller.is_running():
            QMessageBox.information(self, "Capture Running", "Stop capture before clearing the ROI.")
            self.log_msg("Clear ROI blocked: capture is running.")
            return

        self.region = None
        self.capture_controller.set_region(None)
        self.region_label.setText("ROI: (none)")
        self.reset_origin_to_default(silent=True)
        self.clear_calibration(silent=True)

        if self._roi_overlay is not None:
            self._roi_overlay.hide()
            self._roi_overlay.close()
            self._roi_overlay = None

        if self._track_overlay is not None:
            self._track_overlay.hide()

        self.log_msg("ROI cleared.")
        self._write_session_config_json()
        self.update_ui()

    def select_area(self):
        if self.capture_controller.is_running():
            return
        self.log_msg("Define ROI: drag to set, release to confirm. Esc cancels. (One monitor only.)")
        self._selector = ScreenSelector()
        self._selector.selected_global.connect(self.on_selected_global)
        self._selector.cancelled.connect(lambda: self.log_msg("ROI selection cancelled."))
        self._selector.start()

    def _selector_stop_safely(self):
        if self._selector is not None:
            try:
                self._selector.stop()
            except Exception:
                pass
            self._selector = None

    def on_selected_global(self, rect_global: QRect):
        tl = rect_global.topLeft()
        br = rect_global.bottomRight()
        screen_tl = QGuiApplication.screenAt(tl)
        screen_br = QGuiApplication.screenAt(br)

        if screen_tl is None or screen_br is None or screen_tl != screen_br:
            self._selector_stop_safely()
            QApplication.processEvents()
            QMessageBox.warning(
                self,
                "ROI must be on one monitor",
                "Please select an ROI entirely within a single monitor.\n"
                "Multi-monitor ROIs are not supported to avoid DPI/scaling inaccuracies.",
            )
            self.log_msg("ROI rejected: selection spans multiple monitors.")
            return

        self.region = CaptureRegion(rect_global.x(), rect_global.y(), rect_global.width(), rect_global.height())
        self.capture_controller.set_region(self.region)
        self.region_label.setText(f"ROI: x={self.region.x}, y={self.region.y}, w={self.region.w}, h={self.region.h}")
        self.log_msg("ROI set (single monitor).")

        self.reset_origin_to_default(silent=True)
        self._show_roi_overlay()
        if self._tracks_visible:
            self._show_track_overlay()
        self._write_session_config_json()
        self.update_ui()

    # ----------------------------
    # Origin
    # ----------------------------

    def _refresh_origin_display(self):
        self.origin_label.setText(
            f"Origin: {self.origin.mode_name} (x={self.origin.x_norm:.3f}, y={self.origin.y_norm:.3f})"
        )
        if self._roi_overlay is not None:
            self._roi_overlay.set_origin(self.origin)

    def set_origin_norm(self, x_norm: float, y_norm: float, mode_name: str):
        self.origin = OriginConfig(
            x_norm=max(0.0, min(1.0, float(x_norm))),
            y_norm=max(0.0, min(1.0, float(y_norm))),
            mode_name=mode_name,
        )
        self.capture_controller.origin = self.origin
        self._refresh_origin_display()
        self._write_session_config_json()
        self.log_msg(f"Origin updated: {self.origin.mode_name} (x={self.origin.x_norm:.3f}, y={self.origin.y_norm:.3f})")

    def reset_origin_to_default(self, silent: bool = False):
        self.origin_combo.blockSignals(True)
        self.origin_combo.setCurrentText("Top-Right")
        self.origin_combo.blockSignals(False)

        self.set_origin_norm(1.0, 0.0, "Top-Right")
        if not silent:
            self.log_msg("Origin reset to Top-Right.")
        self.update_ui()

    def on_origin_mode_changed(self):
        if self.capture_controller.is_running():
            return
        mode = str(self.origin_combo.currentText())

        if mode == "Top-Left":
            self.set_origin_norm(0.0, 0.0, "Top-Left")
        elif mode == "Top-Right":
            self.set_origin_norm(1.0, 0.0, "Top-Right")
        elif mode == "Bottom-Left":
            self.set_origin_norm(0.0, 1.0, "Bottom-Left")
        elif mode == "Bottom-Right":
            self.set_origin_norm(1.0, 1.0, "Bottom-Right")
        elif mode == "Center":
            self.set_origin_norm(0.5, 0.5, "Center")
        elif mode == "Custom (click in ROI)":
            self.origin.mode_name = "Custom (pending)"
            self._refresh_origin_display()
            self.log_msg("Origin mode set to Custom. Click 'Pick Origin' then click inside ROI.")
        else:
            self.set_origin_norm(1.0, 0.0, "Top-Right")

        self.update_ui()

    def start_origin_picker(self):
        if self.capture_controller.is_running():
            QMessageBox.information(self, "Capture Running", "Stop capture before changing origin.")
            return
        if self.region is None:
            QMessageBox.warning(self, "No ROI", "Define an ROI first.")
            return
        if str(self.origin_combo.currentText()) != "Custom (click in ROI)":
            QMessageBox.information(
                self,
                "Origin preset selected",
                "To pick a custom origin, choose 'Custom (click in ROI)' from the Origin dropdown first.",
            )
            return

        self._show_roi_overlay()
        self.log_msg("Pick Origin: click inside ROI (Esc cancels).")

        self._origin_overlay = OriginPickerOverlay(self.region)
        self._origin_overlay.selected.connect(self.on_origin_picked)
        self._origin_overlay.cancelled.connect(lambda: self.log_msg("Origin pick cancelled."))
        self._origin_overlay.start()

    def on_origin_picked(self, x_norm: float, y_norm: float):
        self.set_origin_norm(x_norm, y_norm, "Custom")
        self.update_ui()

    # ----------------------------
    # Axis mapping
    # ----------------------------

    def _refresh_axis_direction_choices(self):
        def fill_pos(combo: QComboBox, source: str, current_value: str, fallback: str):
            combo.blockSignals(True)
            combo.clear()

            options = ["right", "left"] if source == "horizontal" else ["down", "up"]
            combo.addItems(options)

            if current_value in options:
                combo.setCurrentText(current_value)
            else:
                combo.setCurrentText(fallback)

            combo.blockSignals(False)

        fill_pos(
            self.x_axis_pos_combo,
            self.x_axis_source_combo.currentText(),
            self.axis_conv.x_positive,
            "right" if self.x_axis_source_combo.currentText() == "horizontal" else "down",
        )
        fill_pos(
            self.y_axis_pos_combo,
            self.y_axis_source_combo.currentText(),
            self.axis_conv.y_positive,
            "right" if self.y_axis_source_combo.currentText() == "horizontal" else "down",
        )

    def _refresh_axis_display(self):
        self.axis_label.setText(f"Axes: {self.axis_conv.describe()}")

    def on_axis_config_changed(self, *_args):
        if self.capture_controller.is_running():
            return

        sender = self.sender()

        # Read ALL current UI values first
        x_src = str(self.x_axis_source_combo.currentText())
        y_src = str(self.y_axis_source_combo.currentText())
        x_pos = str(self.x_axis_pos_combo.currentText())
        y_pos = str(self.y_axis_pos_combo.currentText())

        # Enforce one horizontal axis and one vertical axis
        if x_src == y_src:
            if sender == self.x_axis_source_combo:
                y_src = "vertical" if x_src == "horizontal" else "horizontal"
                self.y_axis_source_combo.blockSignals(True)
                self.y_axis_source_combo.setCurrentText(y_src)
                self.y_axis_source_combo.blockSignals(False)
            elif sender == self.y_axis_source_combo:
                x_src = "vertical" if y_src == "horizontal" else "horizontal"
                self.x_axis_source_combo.blockSignals(True)
                self.x_axis_source_combo.setCurrentText(x_src)
                self.x_axis_source_combo.blockSignals(False)
            else:
                y_src = "vertical" if x_src == "horizontal" else "horizontal"
                self.y_axis_source_combo.blockSignals(True)
                self.y_axis_source_combo.setCurrentText(y_src)
                self.y_axis_source_combo.blockSignals(False)

        # Validate positive directions against the chosen source
        if x_src == "horizontal":
            if x_pos not in ("right", "left"):
                x_pos = "right"
        else:
            if x_pos not in ("down", "up"):
                x_pos = "down"

        if y_src == "horizontal":
            if y_pos not in ("right", "left"):
                y_pos = "right"
        else:
            if y_pos not in ("down", "up"):
                y_pos = "down"

        # Store the updated values BEFORE refreshing combos
        self.axis_conv.x_axis_source = x_src
        self.axis_conv.y_axis_source = y_src
        self.axis_conv.x_positive = x_pos
        self.axis_conv.y_positive = y_pos

        # Rebuild the positive-direction combo boxes safely
        self._refresh_axis_direction_choices()

        # Re-apply the chosen positive directions explicitly
        self.x_axis_pos_combo.blockSignals(True)
        self.x_axis_pos_combo.setCurrentText(self.axis_conv.x_positive)
        self.x_axis_pos_combo.blockSignals(False)

        self.y_axis_pos_combo.blockSignals(True)
        self.y_axis_pos_combo.setCurrentText(self.axis_conv.y_positive)
        self.y_axis_pos_combo.blockSignals(False)

        self.capture_controller.axis_conv = self.axis_conv

        if not self.axis_conv.is_valid():
            QMessageBox.warning(self, "Invalid axis mapping", "X and Y cannot both use the same source axis.")
            return

        self._refresh_axis_display()
        self._write_session_config_json()
        self.log_msg(f"Axis mapping updated: {self.axis_conv.describe()}")
        self.update_ui()
    # ----------------------------
    # Calibration
    # ----------------------------

    def _refresh_calibration_display(self):
        if self.calibration.unit_name == "px":
            self.cal_label.setText("Scale: not set")
        else:
            self.cal_label.setText(
                f"Scale: {self.calibration.units_per_pixel:.6g} {self.calibration.unit_name}/px "
                f"({self.calibration.pixels_per_unit:.6g} px/{self.calibration.unit_name})"
            )

    def _write_calibration_json(self):
        try:
            payload = self.calibration.to_dict()
            payload["roi"] = None if self.region is None else {
                "x": self.region.x,
                "y": self.region.y,
                "w": self.region.w,
                "h": self.region.h,
            }
            out_path = get_latest_calibration_path(self.output_dir)
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.log_msg(f"Calibration saved to {out_path.name}")
        except Exception as e:
            self.log_msg(f"WARNING: Could not write calibration JSON: {e}")

    def clear_calibration(self, silent: bool = False):
        if self.capture_controller.is_running():
            if not silent:
                QMessageBox.information(self, "Capture Running", "Stop capture before clearing calibration.")
            return

        self.calibration = Calibration(units_per_pixel=1.0, unit_name="px")
        self.capture_controller.calibration = self.calibration
        self._refresh_calibration_display()
        if not silent:
            self.log_msg("Calibration cleared (scale not set).")
        self._write_session_config_json()
        self.update_ui()

    def start_calibration(self):
        if self.capture_controller.is_running():
            QMessageBox.information(self, "Capture Running", "Stop capture before calibrating.")
            return
        if self.region is None:
            QMessageBox.warning(self, "No ROI", "Define an ROI first.")
            return

        self._show_roi_overlay()
        self.log_msg("Calibration mode: draw a line inside ROI. Esc cancels.")

        self._cal_overlay = CalibrationOverlay(self.region)
        self._cal_overlay.calibrated.connect(self.on_calibration_line)
        self._cal_overlay.cancelled.connect(self._on_calibration_cancelled)
        self._cal_overlay.start()

    def _on_calibration_cancelled(self):
        self.log_msg("Calibration cancelled.")
        self._stop_cal_overlay()

    def _stop_cal_overlay(self):
        if self._cal_overlay is not None:
            try:
                self._cal_overlay.stop()
            except Exception:
                pass
            self._cal_overlay = None

    def on_calibration_line(self, x1: float, y1: float, x2: float, y2: float):
        pixel_len = float(math.hypot(x2 - x1, y2 - y1))
        if pixel_len <= 0:
            self.log_msg("Calibration failed: pixel length was zero.")
            self._stop_cal_overlay()
            return

        dlg = CalibrationDialog(self, pixel_len)
        dlg.raise_()
        dlg.activateWindow()
        rc = dlg.exec()

        if rc != QDialog.DialogCode.Accepted:
            self.log_msg("Calibration cancelled at input dialog.")
            self._stop_cal_overlay()
            return

        res = dlg.get_result()
        if res is None:
            self.log_msg("Calibration cancelled (no result).")
            self._stop_cal_overlay()
            return

        real_len, unit = res
        units_per_pixel = real_len / pixel_len
        self.calibration = Calibration(units_per_pixel=units_per_pixel, unit_name=unit)
        self.capture_controller.calibration = self.calibration
        self._refresh_calibration_display()
        self._write_calibration_json()
        self._write_session_config_json()

        self.log_msg(
            f"Calibration set: {units_per_pixel:.6g} {unit}/px "
            f"(line: {pixel_len:.2f}px = {real_len:g} {unit})"
        )

        self._stop_cal_overlay()
        self.update_ui()

    # ----------------------------
    # Session config JSON
    # ----------------------------

    def _write_session_config_json(self):
        try:
            payload = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "roi": None if self.region is None else {
                    "x": self.region.x,
                    "y": self.region.y,
                    "w": self.region.w,
                    "h": self.region.h,
                },
                "calibration": self.calibration.to_dict(),
                "origin": self.origin.to_dict(),
                "axis_convention": self.axis_conv.to_dict(),
            }
            out_path = get_latest_session_config_path(self.output_dir)
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            self.log_msg(f"WARNING: Could not write session config JSON: {e}")

    # ----------------------------
    # Capture controls
    # ----------------------------

    def interval_ms(self) -> int:
        minutes = int(self.minutes_combo.currentData())
        seconds = int(self.seconds_combo.currentData())
        return (minutes * 60 + seconds) * 1000

    def interval_label(self) -> str:
        minutes = int(self.minutes_combo.currentData())
        seconds = int(self.seconds_combo.currentData())
        return f"{minutes:02d}:{seconds:02d}"

    
    
    def start_capture(self):
        if not self.region:
            QMessageBox.warning(self, "No ROI", "Define an ROI first.")
            return

        ms = self.interval_ms()
        if ms <= 0:
            QMessageBox.warning(self, "Invalid interval", "Choose a non-zero capture interval.")
            return

        if self._roi_overlay is not None:
            self._roi_overlay.set_show_origin_marker(False)

        self._show_roi_overlay()
        self.capture_controller.start_capture(ms)
        self.log_msg(f"Capture started (interval {self.interval_label()} mm:ss). Origin marker hidden.")
        self.update_ui()

        if self._test_mode:
            self._run_pipeline_now()

    def stop_capture(self):
        self.capture_controller.stop_capture()

        if self._roi_overlay is not None:
            self._roi_overlay.set_show_origin_marker(True)

        self._show_roi_overlay()
        self.log_msg("Capture stopped. ROI remains set. Origin marker visible again.")
        self.update_ui()

    def open_folder(self):
        import subprocess
        import platform

        try:
            if platform.system() == "Windows":
                os.startfile(self.output_dir)
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(self.output_dir)], check=True)
            else:
                if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
                    result = subprocess.run(
                        ["explorer.exe", str(self.output_dir)],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        return

                result = subprocess.run(
                    ["xdg-open", str(self.output_dir)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self.log_msg("Cannot open file manager (headless environment)")
                    self.log_msg(f"Frames saved to: {self.output_dir}")
                    return
        except FileNotFoundError:
            self.log_msg("Cannot open file manager (command not available)")
            self.log_msg(f"Frames saved to: {self.output_dir}")
        except Exception as e:
            self.log_msg(f"Could not open folder: {e}")
            self.log_msg(f"Frames saved to: {self.output_dir}")

    def closeEvent(self, event):
        self._selector_stop_safely()
        self._stop_cal_overlay()
        self._pipeline_timer.stop()
        self.capture_controller.stop_capture()

        if self._pipeline_worker is not None and self._pipeline_worker.isRunning():
            self._pipeline_worker.quit()
            self._pipeline_worker.wait(3000)
            self._pipeline_worker = None
        if self._roi_overlay is not None:
            self._roi_overlay.close()
            self._roi_overlay = None
        if self._track_overlay is not None:
            self._track_overlay.close()
            self._track_overlay = None
        if self._origin_overlay is not None:
            try:
                self._origin_overlay.stop()
            except Exception:
                pass
            self._origin_overlay = None
        super().closeEvent(event)


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec())


# =============================================================================
# Backend helper functions
# =============================================================================

def compute_step_velocity(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
) -> Optional[float]:
    x1, y1, t1 = p1
    x2, y2, t2 = p2
    dt = t2 - t1
    if dt == 0:
        return None
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return distance / abs(dt)


def compute_average_track_velocity(
    track: List[Tuple[float, float, float]],
) -> Optional[float]:
    if len(track) < 2:
        return None
    velocities = [
        v
        for v in (compute_step_velocity(track[i], track[i + 1]) for i in range(len(track) - 1))
        if v is not None
    ]
    if not velocities:
        return None
    return sum(velocities) / len(velocities)


def find_fastest_track(
    tracks: Dict[int, List[Tuple[float, float, float]]],
) -> Optional[int]:
    best_id: Optional[int] = None
    best_vel: float = -1.0
    for cell_id, pts in tracks.items():
        avg = compute_average_track_velocity(pts)
        if avg is not None and avg > best_vel:
            best_vel = avg
            best_id = cell_id
    return best_id


def compute_and_store_velocities(db_path: Path) -> Optional[int]:
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()

            cur.executescript("""
                CREATE TABLE IF NOT EXISTS track_step_velocities (
                    cell_id INTEGER NOT NULL,
                    from_frame INTEGER NOT NULL,
                    to_frame INTEGER NOT NULL,
                    velocity REAL NOT NULL,
                    PRIMARY KEY (cell_id, from_frame, to_frame)
                );
                CREATE TABLE IF NOT EXISTS track_avg_velocities (
                    cell_id INTEGER PRIMARY KEY,
                    avg_velocity REAL NOT NULL,
                    step_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                SELECT p.cell_id, p.frame_index,
                       p.x, p.y,
                       COALESCE(f.timestamp, p.frame_index) AS t
                FROM points p
                LEFT JOIN frames f ON f.frame_index = p.frame_index
                ORDER BY p.cell_id, p.frame_index
            """)
            points_by_cell: Dict[int, List[Tuple[int, float, float, float]]] = {}
            for cell_id, frame_idx, x, y, t in cur.fetchall():
                if cell_id not in points_by_cell:
                    points_by_cell[cell_id] = []
                points_by_cell[cell_id].append((int(frame_idx), float(x), float(y), float(t)))

            cells_with_new_steps: set = set()

            for cell_id, pts in points_by_cell.items():
                for i in range(len(pts) - 1):
                    fi, xi, yi, ti = pts[i]
                    fj, xj, yj, tj = pts[i + 1]
                    dt = tj - ti
                    if dt == 0:
                        continue
                    vel = math.sqrt((xj - xi) ** 2 + (yj - yi) ** 2) / abs(dt)
                    cur.execute("""
                        INSERT OR IGNORE INTO track_step_velocities
                            (cell_id, from_frame, to_frame, velocity)
                        VALUES (?, ?, ?, ?)
                    """, (cell_id, fi, fj, vel))
                    if cur.rowcount > 0:
                        cells_with_new_steps.add(cell_id)

            for cell_id in cells_with_new_steps:
                cur.execute("""
                    SELECT AVG(velocity), COUNT(*)
                    FROM track_step_velocities
                    WHERE cell_id = ?
                """, (cell_id,))
                avg_vel, step_count = cur.fetchone()
                if avg_vel is None:
                    continue
                cur.execute("""
                    INSERT INTO track_avg_velocities (cell_id, avg_velocity, step_count, updated_at)
                    VALUES (?, ?, ?, datetime('now'))
                    ON CONFLICT(cell_id) DO UPDATE SET
                        avg_velocity = excluded.avg_velocity,
                        step_count   = excluded.step_count,
                        updated_at   = excluded.updated_at
                """, (cell_id, avg_vel, step_count))

            conn.commit()

            cur.execute("SELECT cell_id FROM track_avg_velocities ORDER BY avg_velocity DESC LIMIT 1")
            row = cur.fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _read_png_size(path: Path) -> Optional[Tuple[int, int]]:
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"\x89PNG":
                return None
            f.seek(16)
            w = struct.unpack(">I", f.read(4))[0]
            h = struct.unpack(">I", f.read(4))[0]
            return w, h
    except Exception:
        return None


def load_tracks_from_db(
    db_path: Path,
) -> Tuple[Dict[int, List[Tuple[float, float, float]]], Optional[Tuple[int, int]]]:
    if not db_path.exists():
        return {}, None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.cell_id, p.x, p.y, COALESCE(f.timestamp, p.frame_index)
                FROM points p
                LEFT JOIN frames f ON f.frame_index = p.frame_index
                ORDER BY p.cell_id, p.frame_index
            """)
            result: Dict[int, List[Tuple[float, float, float]]] = {}
            for cell_id, x, y, t in cursor.fetchall():
                if cell_id not in result:
                    result[cell_id] = []
                result[cell_id].append((float(x), float(y), float(t)))

            frame_size: Optional[Tuple[int, int]] = None
            cursor.execute("SELECT source_path FROM frames ORDER BY frame_index LIMIT 1")
            row = cursor.fetchone()
            if row:
                frame_size = _read_png_size(Path(row[0]))

            return result, frame_size
        finally:
            conn.close()
    except Exception:
        return {}, None


if __name__ == "__main__":
    main()