import sys
import os
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from PySide6.QtCore import Qt, QRect, QPoint, QTimer, Signal, QThread
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QPushButton,
    QLabel,
    QComboBox,
    QVBoxLayout,
    QHBoxLayout,
    QRubberBand,
    QPlainTextEdit,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
)


# ----------------------------
# Data models
# ----------------------------

@dataclass(frozen=True)
class CaptureRegion:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Calibration:
    """Session-only calibration, also exported to JSON for downstream use."""
    units_per_pixel: float = 1.0
    unit_name: str = "px"  # default until calibrated

    @property
    def pixels_per_unit(self) -> float:
        if self.units_per_pixel == 0:
            return float("inf")
        return 1.0 / self.units_per_pixel

    def to_dict(self) -> dict:
        return {
            "units_per_pixel": self.units_per_pixel,
            "pixels_per_unit": self.pixels_per_unit,
            "unit_name": self.unit_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }


@dataclass
class OriginConfig:
    """
    Session-only origin configuration stored as normalized coordinates within the ROI.
    """
    x_norm: float = 1.0
    y_norm: float = 0.0
    mode_name: str = "Top-Right"  # preset name or "Custom"

    def to_dict(self) -> dict:
        return {
            "x_norm": float(self.x_norm),
            "y_norm": float(self.y_norm),
            "mode_name": self.mode_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }


@dataclass
class AxisConvention:
    """
    Defines how ROI-local pixel (u,v) maps to user (X,Y).

    Pixel convention assumed by images/screens:
      u: horizontal (right positive)
      v: vertical (down positive)

    We store:
      X uses: 'horizontal' or 'vertical'
      X positive direction: for horizontal -> 'right'/'left'; for vertical -> 'down'/'up'
      Y uses: 'horizontal' or 'vertical'
      Y positive direction: similarly
    """
    x_axis_source: str = "vertical"     # default for your main user
    x_positive: str = "down"            # +X down
    y_axis_source: str = "horizontal"   # +Y left
    y_positive: str = "left"

    def to_dict(self) -> dict:
        return {
            "x_axis": {"source": self.x_axis_source, "positive": self.x_positive},
            "y_axis": {"source": self.y_axis_source, "positive": self.y_positive},
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def is_valid(self) -> bool:
        # Must use one horizontal and one vertical
        return self.x_axis_source != self.y_axis_source

    def describe(self) -> str:
        x = f"X={self.x_axis_source} (+{self.x_positive})"
        y = f"Y={self.y_axis_source} (+{self.y_positive})"
        return f"{x}, {y}"


# ----------------------------
# Paths / output
# ----------------------------

def get_project_root() -> Path:
    return Path(__file__).parent.parent


def get_output_folder() -> Path:
    project_root = get_project_root()
    out = project_root / "captures"
    out.mkdir(parents=True, exist_ok=True)
    return out


def get_latest_calibration_path(output_dir: Path) -> Path:
    return output_dir / "latest_calibration.json"


def get_latest_session_config_path(output_dir: Path) -> Path:
    return output_dir / "latest_session_config.json"


# ----------------------------
# Calibration dialog
# ----------------------------

class CalibrationDialog(QDialog):
    UNIT_OPTIONS = ["nm", "µm", "mm", "cm", "m"]

    def __init__(self, parent: QWidget, pixel_length: float):
        super().__init__(parent)
        self.setWindowTitle("Calibrate Scale")
        self.setModal(True)

        self.length_edit = QLineEdit()
        self.length_edit.setPlaceholderText("e.g., 5")

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(self.UNIT_OPTIONS)
        self.unit_combo.setCurrentText("µm")

        info = QLabel(f"Line length: {pixel_length:.2f} px")
        info.setStyleSheet("color: #666;")

        form = QFormLayout()
        form.addRow("Real length:", self.length_edit)
        form.addRow("Units:", self.unit_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._result: Optional[Tuple[float, str]] = None

    def accept(self):
        raw = self.length_edit.text().strip()
        try:
            val = float(raw)
            if val <= 0:
                raise ValueError()
        except Exception:
            QMessageBox.warning(self, "Invalid length", "Please enter a positive number (e.g., 5).")
            return

        unit = str(self.unit_combo.currentText())
        self._result = (val, unit)
        super().accept()

    def get_result(self) -> Optional[Tuple[float, str]]:
        return self._result


# ----------------------------
# ROI Overlay (border + origin marker)
# ----------------------------

class ROIOverlay(QWidget):
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

        self._border_pen = QPen(QColor(0, 255, 0, 230))
        self._border_pen.setWidth(2)

        self._origin: Optional[OriginConfig] = None

        # Origin marker: neon green, thicker than border
        self._origin_pen = QPen(QColor(0, 255, 0, 255))
        self._origin_pen.setWidth(3)

        # NEW: allow hiding marker during capture
        self._show_origin_marker: bool = True

    def set_region_global(self, region: CaptureRegion):
        self.setGeometry(region.x, region.y, region.w, region.h)
        self.update()

    def set_origin(self, origin: Optional[OriginConfig]):
        self._origin = origin
        self.update()

    def set_show_origin_marker(self, show: bool):
        self._show_origin_marker = bool(show)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(self._border_pen)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

        # Origin marker only if allowed
        if self._origin is not None and self._show_origin_marker:
            w = max(1, self.width())
            h = max(1, self.height())

            x_norm = max(0.0, min(1.0, float(self._origin.x_norm)))
            y_norm = max(0.0, min(1.0, float(self._origin.y_norm)))

            ox = int(round(x_norm * (w - 1)))
            oy = int(round(y_norm * (h - 1)))

            size = 12
            painter.setPen(self._origin_pen)
            painter.drawLine(ox - size, oy, ox + size, oy)
            painter.drawLine(ox, oy - size, ox, oy + size)

            painter.setBrush(QColor(0, 255, 0, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(ox, oy), 3, 3)


# ----------------------------
# Track Overlay (cell tracks from database)
# ----------------------------

class TrackOverlay(QWidget):
    """Transparent overlay that draws cell track dots and connecting lines from the DB."""

    DOT_RADIUS = 2
    RING_RADIUS = 7

    # Palette of visually distinct (R, G, B) tuples — cycled per cell_id
    _PALETTE = [
        (220,  50,  50),  # red
        ( 50, 180,  50),  # green
        ( 50, 120, 220),  # blue
        (220, 160,   0),  # amber
        (180,  50, 220),  # purple
        (  0, 200, 200),  # cyan
        (220, 110,   0),  # orange
        (220,  50, 150),  # pink
        (100, 220,  80),  # lime
        ( 80, 180, 220),  # sky blue
    ]

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

        # cell_id -> list of (x, y) in physical pixels of the captured frame image
        self._points_by_cell: Dict[int, List[Tuple[float, float]]] = {}
        # Device pixel ratio of the screen the ROI lives on (used to scale DB coords
        # back to the overlay widget's logical pixel space)
        self._dpr: float = 1.0
        # Stable cell_id -> palette index mapping (so colors don't shift on refresh)
        self._cell_color_index: Dict[int, int] = {}
        self._next_color_index: int = 0

    def _color_for_cell(self, cell_id: int) -> Tuple[int, int, int]:
        if cell_id not in self._cell_color_index:
            self._cell_color_index[cell_id] = self._next_color_index % len(self._PALETTE)
            self._next_color_index += 1
        return self._PALETTE[self._cell_color_index[cell_id]]

    def set_region_global(self, region: CaptureRegion):
        self.setGeometry(region.x, region.y, region.w, region.h)
        self.update()

    def set_tracks(self, points_by_cell: Dict[int, List[Tuple[float, float]]]):
        self._points_by_cell = points_by_cell
        self.update()

    def set_dpr(self, dpr: float):
        self._dpr = max(0.01, float(dpr))
        self.update()

    def paintEvent(self, _event):
        if not self._points_by_cell:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        scale = 1.0 / self._dpr

        # Draw each cell's track in its own color
        for cell_id, pts in self._points_by_cell.items():
            r, g, b = self._color_for_cell(cell_id)
            line_color = QColor(r, g, b, 150)
            dot_color = QColor(r, g, b, 220)
            ring_color = QColor(r, g, b, 200)

            # Track lines
            if len(pts) >= 2:
                line_pen = QPen(line_color)
                line_pen.setWidth(1)
                painter.setPen(line_pen)
                for i in range(len(pts) - 1):
                    x1 = int(round(pts[i][0] * scale))
                    y1 = int(round(pts[i][1] * scale))
                    x2 = int(round(pts[i + 1][0] * scale))
                    y2 = int(round(pts[i + 1][1] * scale))
                    painter.drawLine(QPoint(x1, y1), QPoint(x2, y2))

            # Dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot_color)
            for x, y in pts:
                cx = int(round(x * scale))
                cy = int(round(y * scale))
                painter.drawEllipse(QPoint(cx, cy), self.DOT_RADIUS, self.DOT_RADIUS)

            # Ring around the most recent point
            if pts:
                ring_pen = QPen(ring_color)
                ring_pen.setWidth(1)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                x, y = pts[-1]
                cx = int(round(x * scale))
                cy = int(round(y * scale))
                painter.drawEllipse(QPoint(cx, cy), self.RING_RADIUS, self.RING_RADIUS)


# ----------------------------
# Pipeline Worker (background thread)
# ----------------------------

class PipelineWorker(QThread):
    """Runs IncrementalTracker.process_batch() in a background thread."""

    finished = Signal(bool, str)  # (success, message)

    def __init__(self, batch_path: Path):
        super().__init__()
        self._batch_path = batch_path

    def run(self):
        try:
            project_root = get_project_root()
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from src.main import IncrementalTracker  # type: ignore
            from src.config import get_default_config  # type: ignore
            config = get_default_config()
            tracker = IncrementalTracker(config)
            tracker.process_batch(self._batch_path)
            self.finished.emit(True, "Pipeline completed successfully.")
        except Exception as exc:
            self.finished.emit(False, f"Pipeline error: {exc}")


# ----------------------------
# Calibration Overlay (interactive line draw)
# ----------------------------

class CalibrationOverlay(QWidget):
    calibrated = Signal(float, float, float, float)
    cancelled = Signal()

    def __init__(self, region: CaptureRegion):
        super().__init__(None)
        self._region = region

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(region.x, region.y, region.w, region.h)

        self._line_pen = QPen(QColor(255, 215, 0, 240))
        self._line_pen.setWidth(3)

        self._hint_pen = QPen(QColor(255, 255, 255, 220))
        self._hint_pen.setWidth(1)

        self._start: Optional[QPoint] = None
        self._end: Optional[QPoint] = None
        self._drawing: bool = False
        self._finalized: bool = False

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabMouse()
        self.grabKeyboard()

    def stop(self):
        self.release_input_grab()
        self.close()

    def release_input_grab(self):
        try:
            self.releaseMouse()
        except Exception:
            pass
        try:
            self.releaseKeyboard()
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.stop()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._finalized:
            return
        self._start = event.position().toPoint()
        self._end = self._start
        self._drawing = True
        self.update()

    def mouseMoveEvent(self, event):
        if not self._drawing or self._start is None or self._finalized:
            return
        self._end = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._start is None or self._end is None or self._finalized:
            return

        self._drawing = False
        length = math.hypot(self._end.x() - self._start.x(), self._end.y() - self._start.y())
        if length < 10:
            self.cancelled.emit()
            self.stop()
            return

        self._finalized = True
        self.update()
        self.release_input_grab()

        self.calibrated.emit(
            float(self._start.x()), float(self._start.y()), float(self._end.x()), float(self._end.y())
        )

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 60))

        painter.setPen(self._hint_pen)
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(12, 24, "Calibration: drag a line to set known distance. Esc to cancel.")

        if self._start is not None and self._end is not None:
            painter.setPen(self._line_pen)
            painter.drawLine(self._start, self._end)


# ----------------------------
# Origin picker overlay (single-click sets origin)
# ----------------------------

class OriginPickerOverlay(QWidget):
    selected = Signal(float, float)
    cancelled = Signal()

    def __init__(self, region: CaptureRegion):
        super().__init__(None)
        self._region = region

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(region.x, region.y, region.w, region.h)

        self._hint_pen = QPen(QColor(255, 255, 255, 220))
        self._hint_pen.setWidth(1)

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabMouse()
        self.grabKeyboard()

    def stop(self):
        self.release_input_grab()
        self.close()

    def release_input_grab(self):
        try:
            self.releaseMouse()
        except Exception:
            pass
        try:
            self.releaseKeyboard()
        except Exception:
            pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.stop()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        p = event.position().toPoint()
        w = max(1, self.width())
        h = max(1, self.height())

        x_norm = max(0.0, min(1.0, p.x() / float(w - 1) if w > 1 else 0.0))
        y_norm = max(0.0, min(1.0, p.y() / float(h - 1) if h > 1 else 0.0))

        self.selected.emit(x_norm, y_norm)
        self.stop()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 60))
        painter.setPen(self._hint_pen)
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(12, 24, "Pick Origin: click inside ROI. (Esc cancels)")


# ----------------------------
# Screen selector
# ----------------------------

class ScreenSelector(QWidget):
    selected_global = Signal(QRect)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._origin_global: QPoint | None = None
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rubber.hide()

        screen = QGuiApplication.primaryScreen()
        self._virtual = screen.virtualGeometry() if screen else QRect(0, 0, 1920, 1080)
        self.setGeometry(self._virtual)

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabMouse()
        self.grabKeyboard()

    def stop(self):
        try:
            self.releaseMouse()
        except Exception:
            pass
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self._rubber.hide()
        self.close()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        painter.setPen(QPen(QColor(255, 255, 255, 230)))
        painter.drawText(
            20,
            35,
            "Drag to define ROI. Release to set. Press Esc to cancel. (ROI must stay on one monitor.)",
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.stop()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._origin_global = event.globalPosition().toPoint()
        origin_local = self.mapFromGlobal(self._origin_global)
        self._rubber.setGeometry(QRect(origin_local, QPoint()))
        self._rubber.show()

    def mouseMoveEvent(self, event):
        if self._origin_global is None:
            return
        current_global = event.globalPosition().toPoint()
        origin_local = self.mapFromGlobal(self._origin_global)
        current_local = self.mapFromGlobal(current_global)
        self._rubber.setGeometry(QRect(origin_local, current_local).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._origin_global is None:
            return
        end_global = event.globalPosition().toPoint()
        rect_global = QRect(self._origin_global, end_global).normalized()
        self._origin_global = None

        if rect_global.width() < 5 or rect_global.height() < 5:
            self.cancelled.emit()
            self.stop()
            return

        self.selected_global.emit(rect_global)
        self.stop()


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
        self.resize(980, 560)

        self.output_dir = get_output_folder()
        self.region: CaptureRegion | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture)

        self._selector: ScreenSelector | None = None
        self._roi_overlay: ROIOverlay | None = None
        self._roi_box_enabled: bool = True

        # Track overlay state
        self._track_overlay: TrackOverlay | None = None
        self._tracks_visible: bool = False

        # Pipeline execution state
        self._db_path: Path = get_project_root() / "data" / "tracking.db"
        self._pipeline_timer: QTimer = QTimer(self)
        self._pipeline_timer.timeout.connect(self._run_pipeline_now)
        self._pipeline_worker: PipelineWorker | None = None
        self._test_mode: bool = False

        # Calibration state
        self.calibration: Calibration = Calibration(units_per_pixel=1.0, unit_name="px")
        self._cal_overlay: Optional[CalibrationOverlay] = None

        # Origin state
        self.origin: OriginConfig = OriginConfig(x_norm=1.0, y_norm=0.0, mode_name="Top-Right")
        self._origin_overlay: Optional[OriginPickerOverlay] = None

        # Axis convention
        self.axis_conv: AxisConvention = AxisConvention(
            x_axis_source="vertical", x_positive="down",
            y_axis_source="horizontal", y_positive="left"
        )

        self.build_ui()
        self.update_ui()
        self._write_session_config_json()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        label_style = "color: #666;"
        status_style = "font-weight: 600;"

        self.folder_label = QLabel(f"Save folder: {self.output_dir}")
        self.folder_label.setStyleSheet(label_style)
        layout.addWidget(self.folder_label)

        self.region_label = QLabel("ROI: (none)")
        self.region_label.setStyleSheet(label_style)
        layout.addWidget(self.region_label)

        status_row = QHBoxLayout()
        self.origin_label = QLabel("Origin: Top-Right")
        self.origin_label.setStyleSheet("font-weight: 600; color: #2b2b2b;")
        status_row.addWidget(self.origin_label)

        status_row.addSpacing(14)

        self.axis_label = QLabel("Axes: X=vertical (+down), Y=horizontal (+left)")
        self.axis_label.setStyleSheet("font-weight: 600; color: #2b2b2b;")
        status_row.addWidget(self.axis_label)

        status_row.addSpacing(14)

        self.cal_label = QLabel("Scale: not set")
        self.cal_label.setStyleSheet("font-weight: 600; color: #2b2b2b;")
        status_row.addWidget(self.cal_label)

        status_row.addStretch()
        layout.addLayout(status_row)

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
        interval_row.addSpacing(12)
        interval_row.addWidget(QLabel("sec"))
        interval_row.addWidget(self.seconds_combo)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        # Row 1
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
        row1.addSpacing(8)
        row1.addWidget(QLabel("Origin:"))
        row1.addWidget(self.origin_combo)
        row1.addWidget(self.pick_origin_btn)
        row1.addWidget(self.reset_origin_btn)
        row1.addSpacing(10)
        row1.addWidget(self.calibrate_btn)
        row1.addWidget(self.clear_cal_btn)
        row1.addStretch()
        layout.addLayout(row1)

        # Row 2: Axis mapping controls
        row_axis = QHBoxLayout()
        row_axis.addWidget(QLabel("User axes:"))

        self.x_axis_source_combo = QComboBox()
        self.x_axis_source_combo.addItems(self.AXIS_SOURCE_OPTIONS)
        self.x_axis_source_combo.setCurrentText(self.axis_conv.x_axis_source)
        self.x_axis_source_combo.currentIndexChanged.connect(self.on_axis_config_changed)

        self.x_axis_pos_combo = QComboBox()
        self.x_axis_pos_combo.currentIndexChanged.connect(self.on_axis_config_changed)

        self.y_axis_source_combo = QComboBox()
        self.y_axis_source_combo.addItems(self.AXIS_SOURCE_OPTIONS)
        self.y_axis_source_combo.setCurrentText(self.axis_conv.y_axis_source)
        self.y_axis_source_combo.currentIndexChanged.connect(self.on_axis_config_changed)

        self.y_axis_pos_combo = QComboBox()
        self.y_axis_pos_combo.currentIndexChanged.connect(self.on_axis_config_changed)

        row_axis.addWidget(QLabel("X uses:"))
        row_axis.addWidget(self.x_axis_source_combo)
        row_axis.addWidget(QLabel("X positive:"))
        row_axis.addWidget(self.x_axis_pos_combo)
        row_axis.addSpacing(14)
        row_axis.addWidget(QLabel("Y uses:"))
        row_axis.addWidget(self.y_axis_source_combo)
        row_axis.addWidget(QLabel("Y positive:"))
        row_axis.addWidget(self.y_axis_pos_combo)
        row_axis.addStretch()
        layout.addLayout(row_axis)

        # Row 3: Capture controls
        row2 = QHBoxLayout()
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

        row2.addWidget(self.play_btn)
        row2.addWidget(self.stop_btn)
        row2.addWidget(self.open_btn)
        row2.addWidget(self.clear_roi_btn)
        row2.addWidget(self.roi_box_toggle_btn)
        row2.addStretch()
        layout.addLayout(row2)

        # ── Pipeline execution row ──
        pipeline_row = QHBoxLayout()
        pipeline_row.addWidget(QLabel("Pipeline interval:"))

        self.pipeline_minutes_combo = QComboBox()
        for m in range(1, 60):
            self.pipeline_minutes_combo.addItem(f"{m:02d}", m)
        self.pipeline_minutes_combo.setCurrentIndex(4)  # default 5 min

        pipeline_row.addWidget(self.pipeline_minutes_combo)
        pipeline_row.addWidget(QLabel("min"))
        pipeline_row.addSpacing(8)

        self.run_pipeline_btn = QPushButton("Run Pipeline Now")
        self.run_pipeline_btn.clicked.connect(self._run_pipeline_now)

        self.pipeline_auto_btn = QPushButton("Start Auto Pipeline")
        self.pipeline_auto_btn.setCheckable(True)
        self.pipeline_auto_btn.clicked.connect(self._toggle_auto_pipeline)

        self.test_mode_checkbox = QCheckBox("Test Mode (use vid1_frames)")
        self.test_mode_checkbox.setChecked(False)
        self.test_mode_checkbox.toggled.connect(self._on_test_mode_toggled)

        pipeline_row.addWidget(self.run_pipeline_btn)
        pipeline_row.addWidget(self.pipeline_auto_btn)
        pipeline_row.addSpacing(16)
        pipeline_row.addWidget(self.test_mode_checkbox)
        pipeline_row.addStretch()
        layout.addLayout(pipeline_row)

        # ── Track visualization row ──
        tracks_row = QHBoxLayout()

        self.tracks_toggle_btn = QPushButton("Tracks: OFF")
        self.tracks_toggle_btn.setCheckable(True)
        self.tracks_toggle_btn.setChecked(False)
        self.tracks_toggle_btn.clicked.connect(self._toggle_tracks)

        self.refresh_tracks_btn = QPushButton("Refresh Tracks")
        self.refresh_tracks_btn.clicked.connect(self._refresh_track_overlay)

        self.clear_tracks_btn = QPushButton("Clear Tracks")
        self.clear_tracks_btn.clicked.connect(self._clear_tracks)

        tracks_row.addWidget(self.tracks_toggle_btn)
        tracks_row.addWidget(self.refresh_tracks_btn)
        tracks_row.addWidget(self.clear_tracks_btn)
        tracks_row.addStretch()

        self.pipeline_status_label = QLabel("Pipeline: Idle")
        self.pipeline_status_label.setStyleSheet(status_style)
        tracks_row.addWidget(self.pipeline_status_label)
        layout.addLayout(tracks_row)

        self.status = QLabel("Capture status: Idle")
        self.status.setStyleSheet(status_style)
        layout.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # Initialize
        self._refresh_axis_direction_choices()
        self._refresh_origin_display()
        self._refresh_axis_display()
        self._refresh_calibration_display()

    def update_ui(self):
        running = self.timer.isActive()
        custom_selected = (self.origin_combo.currentText() == "Custom (click in ROI)")

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
        self.pipeline_auto_btn.setText(
            "Stop Auto Pipeline" if auto_pipeline_on else "Start Auto Pipeline"
        )
        self.pipeline_auto_btn.setChecked(auto_pipeline_on)
        self.tracks_toggle_btn.setText("Tracks: ON" if self._tracks_visible else "Tracks: OFF")
        self.tracks_toggle_btn.setChecked(self._tracks_visible)
        self.refresh_tracks_btn.setEnabled(self.region is not None)
        self.clear_tracks_btn.setEnabled(self.region is not None)

    def log_msg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

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
        # Keep marker hidden while capturing
        self._roi_overlay.set_show_origin_marker(not self.timer.isActive())
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
        """Return the device pixel ratio of the screen containing the ROI."""
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
        """Query the database for all cell tracks and update the overlay."""
        tracks = load_tracks_from_db(self._db_path)
        if not tracks:
            self.log_msg(f"No tracks found in database ({self._db_path.name}).")
            return
        total_pts = sum(len(v) for v in tracks.values())
        self.log_msg(f"Loaded {len(tracks)} cell track(s) ({total_pts} points) from DB.")
        self._ensure_track_overlay()
        self._track_overlay.set_tracks(tracks)
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
        """Trigger one pipeline run immediately, if no run is already in progress."""
        if self._pipeline_worker is not None and self._pipeline_worker.isRunning():
            self.log_msg("Pipeline already running — skipping.")
            return
        if self._test_mode:
            batch_path = get_project_root() / "vid1_frames"
        else:
            batch_path = get_output_folder()
        frame_exts = {".png", ".tif", ".tiff", ".jpg", ".jpeg"}
        has_frames = batch_path.exists() and any(f.suffix.lower() in frame_exts for f in batch_path.iterdir())
        if not has_frames:
            self.log_msg(f"No frames found in {batch_path}. {'Check vid1_frames/ folder.' if self._test_mode else 'Capture some frames first.'}")
            return
        self.log_msg(f"Starting pipeline on {batch_path} …")
        self.pipeline_status_label.setText("Pipeline: Running")
        self._pipeline_worker = PipelineWorker(batch_path)
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
        if self.timer.isActive():
            QMessageBox.information(self, "Capture Running", "Stop capture before clearing the ROI.")
            self.log_msg("Clear ROI blocked: capture is running.")
            return

        self.region = None
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
        if self.timer.isActive():
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
        if self.timer.isActive():
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
        if self.timer.isActive():
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
        def fill_pos(combo: QComboBox, source: str, desired: str):
            combo.blockSignals(True)
            combo.clear()
            if source == "horizontal":
                combo.addItems(["right", "left"])
            else:
                combo.addItems(["down", "up"])
            if desired in [combo.itemText(i) for i in range(combo.count())]:
                combo.setCurrentText(desired)
            combo.blockSignals(False)

        fill_pos(self.x_axis_pos_combo, self.x_axis_source_combo.currentText(), self.axis_conv.x_positive)
        fill_pos(self.y_axis_pos_combo, self.y_axis_source_combo.currentText(), self.axis_conv.y_positive)

    def _refresh_axis_display(self):
        self.axis_label.setText(f"Axes: {self.axis_conv.describe()}")

    def on_axis_config_changed(self):
        if self.timer.isActive():
            return

        x_src = str(self.x_axis_source_combo.currentText())
        y_src = str(self.y_axis_source_combo.currentText())

        if x_src == y_src:
            y_src = "vertical" if x_src == "horizontal" else "horizontal"
            self.y_axis_source_combo.blockSignals(True)
            self.y_axis_source_combo.setCurrentText(y_src)
            self.y_axis_source_combo.blockSignals(False)

        self.axis_conv.x_axis_source = x_src
        self.axis_conv.y_axis_source = y_src

        self._refresh_axis_direction_choices()

        self.axis_conv.x_positive = str(self.x_axis_pos_combo.currentText())
        self.axis_conv.y_positive = str(self.y_axis_pos_combo.currentText())

        if not self.axis_conv.is_valid():
            QMessageBox.warning(self, "Invalid axis mapping", "X and Y cannot both use the same direction.")
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
                "x": self.region.x, "y": self.region.y, "w": self.region.w, "h": self.region.h
            }
            out_path = get_latest_calibration_path(self.output_dir)
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.log_msg(f"Calibration saved to {out_path.name}")
        except Exception as e:
            self.log_msg(f"WARNING: Could not write calibration JSON: {e}")

    def clear_calibration(self, silent: bool = False):
        if self.timer.isActive():
            if not silent:
                QMessageBox.information(self, "Capture Running", "Stop capture before clearing calibration.")
            return

        self.calibration = Calibration(units_per_pixel=1.0, unit_name="px")
        self._refresh_calibration_display()
        if not silent:
            self.log_msg("Calibration cleared (scale not set).")
        self._write_session_config_json()
        self.update_ui()

    def start_calibration(self):
        if self.timer.isActive():
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
                    "x": self.region.x, "y": self.region.y, "w": self.region.w, "h": self.region.h
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

        # Hide origin marker while capturing
        if self._roi_overlay is not None:
            self._roi_overlay.set_show_origin_marker(False)

        self._show_roi_overlay()
        self.capture()
        self.timer.start(ms)
        self.log_msg(f"Capture started (interval {self.interval_label()} mm:ss). Origin marker hidden.")
        self.update_ui()
        if self._test_mode:
            self._run_pipeline_now()

    def stop_capture(self):
        self.timer.stop()

        # Show origin marker again when stopped
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
                        text=True
                    )
                    if result.returncode == 0:
                        return

                result = subprocess.run(
                    ["xdg-open", str(self.output_dir)],
                    capture_output=True,
                    text=True
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

    def capture(self):
        if not self.region:
            return

        roi_top_left = QPoint(self.region.x, self.region.y)
        screen = QGuiApplication.screenAt(roi_top_left) or QGuiApplication.primaryScreen()
        if screen is None:
            self.log_msg("ERROR: No screen found.")
            return

        geom = screen.geometry()
        dpr = float(screen.devicePixelRatio())

        local_x = self.region.x - geom.x()
        local_y = self.region.y - geom.y()

        px_x = int(round(local_x * dpr))
        px_y = int(round(local_y * dpr))
        px_w = int(round(self.region.w * dpr))
        px_h = int(round(self.region.h * dpr))

        overlay_was_visible = self._roi_overlay is not None and self._roi_overlay.isVisible()
        track_was_visible = self._track_overlay is not None and self._track_overlay.isVisible()
        if overlay_was_visible:
            self._hide_roi_overlay()
        if track_was_visible:
            self._hide_track_overlay()
        if overlay_was_visible or track_was_visible:
            QApplication.processEvents()

        pixmap = screen.grabWindow(0, px_x, px_y, px_w, px_h)

        if overlay_was_visible:
            self._show_roi_overlay()
        if track_was_visible:
            self._show_track_overlay()
        if overlay_was_visible or track_was_visible:
            QApplication.processEvents()

        if pixmap.isNull():
            self.log_msg("ERROR: Capture failed (pixmap is null).")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.output_dir / f"frame_{ts}.png"
        pixmap.save(str(path), "PNG")
        self.log_msg(f"Saved {path.name}")

    def closeEvent(self, event):
        self._selector_stop_safely()
        self._stop_cal_overlay()
        self._pipeline_timer.stop()
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
# Backend helper functions (import these from your tracking code)
# =============================================================================

def load_tracks_from_db(db_path: Path) -> Dict[int, List[Tuple[float, float]]]:
    """
    Load all cell track points from the SQLite tracking database.

    Returns:
        Dict mapping cell_id -> list of (x, y) tuples ordered by frame_index.
        Coordinates are in the physical pixel space of the captured frame images
        (i.e. multiply the ROI logical size by the screen DPR to get this space).
        Returns an empty dict if the database does not exist or has no points.
    """
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT cell_id, x, y FROM points ORDER BY cell_id, frame_index"
            )
            result: Dict[int, List[Tuple[float, float]]] = {}
            for cell_id, x, y in cursor.fetchall():
                if cell_id not in result:
                    result[cell_id] = []
                result[cell_id].append((float(x), float(y)))
            return result
        finally:
            conn.close()
    except Exception:
        return {}


def roi_origin_pixel(roi_w: int, roi_h: int, origin: OriginConfig) -> Tuple[int, int]:
    """
    Convert normalized origin (x_norm,y_norm) into ROI-local pixel origin (u0,v0).
    """
    if roi_w <= 0 or roi_h <= 0:
        return 0, 0
    u0 = int(round(max(0.0, min(1.0, origin.x_norm)) * (roi_w - 1)))
    v0 = int(round(max(0.0, min(1.0, origin.y_norm)) * (roi_h - 1)))
    return u0, v0


def _axis_value(dx: float, dy: float, source: str, positive: str) -> float:
    """
    Internal helper: choose dx/dy and apply sign based on positive direction.
    """
    if source == "horizontal":
        base = dx
        sign = 1.0 if positive == "right" else -1.0  # left => negative
    else:
        base = dy
        sign = 1.0 if positive == "down" else -1.0   # up => negative
    return sign * base


def pixel_to_user_coords(
    u: float,
    v: float,
    roi_w: int,
    roi_h: int,
    origin: OriginConfig,
    axis: AxisConvention,
    calibration: Optional[Calibration] = None,
) -> Dict[str, Any]:
    """
    Convert ROI-local pixel coords (u,v) into user's preferred coordinate system.

    Returns:
      - X_px, Y_px in user coordinate pixels
      - If calibration provided and unit_name != "px", also returns X_units, Y_units.
    """
    u0, v0 = roi_origin_pixel(roi_w, roi_h, origin)
    dx = float(u) - float(u0)
    dy = float(v) - float(v0)

    if not axis.is_valid():
        raise ValueError("Invalid AxisConvention: X and Y cannot both use the same source axis.")

    X_px = _axis_value(dx, dy, axis.x_axis_source, axis.x_positive)
    Y_px = _axis_value(dx, dy, axis.y_axis_source, axis.y_positive)

    out: Dict[str, Any] = {
        "X_px": X_px,
        "Y_px": Y_px,
        "origin_u0": u0,
        "origin_v0": v0,
    }

    if calibration is not None and calibration.unit_name != "px":
        out["X_units"] = X_px * float(calibration.units_per_pixel)
        out["Y_units"] = Y_px * float(calibration.units_per_pixel)
        out["unit_name"] = calibration.unit_name

    return out


if __name__ == "__main__":
    main()
