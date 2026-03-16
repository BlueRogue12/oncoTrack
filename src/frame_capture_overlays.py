import math
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QWidget,
    QRubberBand,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QLabel,
    QVBoxLayout,
    QComboBox,
)

from src.frame_capture_models import CaptureRegion, OriginConfig


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

        # allow hiding marker during capture
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