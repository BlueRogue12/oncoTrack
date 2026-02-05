import sys
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QRect, QPoint, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen
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
)


@dataclass(frozen=True)
class CaptureRegion:
    x: int
    y: int
    w: int
    h: int


def get_output_folder() -> Path:
    docs = Path(os.path.expanduser("~/Documents"))
    out = docs / "OncoTrackSnaps"
    out.mkdir(exist_ok=True)
    return out


class ROIOverlay(QWidget):
    """
    Persistent on-screen ROI highlight (border-only).

    - Always-on-top, transparent background
    - Click-through (does NOT block microscope UI)
    - Temporarily hidden during capture so it doesn't appear in screenshots
    """

    def __init__(self):
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput  # click-through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._border_pen = QPen(QColor(0, 255, 0, 230))
        self._border_pen.setWidth(2)

    def set_region_global(self, region: CaptureRegion):
        self.setGeometry(region.x, region.y, region.w, region.h)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setPen(self._border_pen)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))


class ScreenSelector(QWidget):
    """
    Fullscreen overlay over the virtual desktop (all monitors).

    Uses event.globalPosition() to compute ROI in global coordinates directly.
    """
    selected_global = Signal(QRect)  # global QRect
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
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)
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


class ScreenshotApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OncoTrack: Frame Capture")
        self.resize(700, 390)

        self.output_dir = get_output_folder()
        self.region: CaptureRegion | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture)

        self._selector: ScreenSelector | None = None
        self._roi_overlay: ROIOverlay | None = None
        self._roi_box_enabled: bool = True

        self.build_ui()
        self.update_ui()

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

        btn_row = QHBoxLayout()
        self.select_btn = QPushButton("Define / Redefine ROI")
        self.play_btn = QPushButton("Start Capture")
        self.stop_btn = QPushButton("Stop Capture")
        self.open_btn = QPushButton("Open Folder")
        self.clear_roi_btn = QPushButton("Clear ROI")

        self.roi_box_toggle_btn = QPushButton("ROI Box: ON")
        self.roi_box_toggle_btn.setCheckable(True)
        self.roi_box_toggle_btn.setChecked(True)
        self.roi_box_toggle_btn.clicked.connect(self.toggle_roi_box)

        self.select_btn.clicked.connect(self.select_area)
        self.play_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)
        self.open_btn.clicked.connect(self.open_folder)
        self.clear_roi_btn.clicked.connect(self.clear_roi)

        btn_row.addWidget(self.select_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.clear_roi_btn)
        btn_row.addWidget(self.roi_box_toggle_btn)
        layout.addLayout(btn_row)

        self.status = QLabel("Capture status: Idle")
        self.status.setStyleSheet(status_style)
        layout.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def log_msg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def update_ui(self):
        running = self.timer.isActive()

        self.select_btn.setEnabled(not running)
        self.minutes_combo.setEnabled(not running)
        self.seconds_combo.setEnabled(not running)

        self.play_btn.setEnabled((self.region is not None) and (not running))
        self.stop_btn.setEnabled(running)

        self.clear_roi_btn.setEnabled((self.region is not None) and (not running))
        self.roi_box_toggle_btn.setEnabled(self.region is not None)

        self.status.setText("Capture status: Capturing" if running else "Capture status: Idle")
        self.roi_box_toggle_btn.setText("ROI Box: ON" if self._roi_box_enabled else "ROI Box: OFF")

    def interval_ms(self) -> int:
        minutes = int(self.minutes_combo.currentData())
        seconds = int(self.seconds_combo.currentData())
        return (minutes * 60 + seconds) * 1000

    def interval_label(self) -> str:
        minutes = int(self.minutes_combo.currentData())
        seconds = int(self.seconds_combo.currentData())
        return f"{minutes:02d}:{seconds:02d}"

    def _ensure_overlay(self):
        if self._roi_overlay is None:
            self._roi_overlay = ROIOverlay()

    def _show_roi_overlay(self):
        if not self._roi_box_enabled or self.region is None:
            return
        self._ensure_overlay()
        self._roi_overlay.set_region_global(self.region)
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

    def clear_roi(self):
        if self.timer.isActive():
            QMessageBox.information(self, "Capture Running", "Stop capture before clearing the ROI.")
            self.log_msg("Clear ROI blocked: capture is running.")
            return

        self.region = None
        self.region_label.setText("ROI: (none)")
        if self._roi_overlay is not None:
            self._roi_overlay.hide()
            self._roi_overlay.close()
            self._roi_overlay = None
        self.log_msg("ROI cleared.")
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
        """Stop selector overlay (release grabs) if it's still around."""
        if self._selector is not None:
            try:
                self._selector.stop()
            except Exception:
                pass
            self._selector = None

    def on_selected_global(self, rect_global: QRect):
        # Enforce: ROI must be fully on a single screen.
        tl = rect_global.topLeft()
        br = rect_global.bottomRight()
        screen_tl = QGuiApplication.screenAt(tl)
        screen_br = QGuiApplication.screenAt(br)

        if screen_tl is None or screen_br is None or screen_tl != screen_br:
            # IMPORTANT: ensure the overlay/grab is gone BEFORE showing a modal dialog
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

        self.region_label.setText(
            f"ROI: x={self.region.x}, y={self.region.y}, w={self.region.w}, h={self.region.h}"
        )
        self.log_msg("ROI set (single monitor).")
        self._show_roi_overlay()
        self.update_ui()

    def start_capture(self):
        if not self.region:
            QMessageBox.warning(self, "No ROI", "Define an ROI first.")
            return

        ms = self.interval_ms()
        if ms <= 0:
            QMessageBox.warning(self, "Invalid interval", "Choose a non-zero capture interval.")
            return

        self._show_roi_overlay()
        self.capture()
        self.timer.start(ms)
        self.log_msg(f"Capture started (interval {self.interval_label()} mm:ss).")
        self.update_ui()

    def stop_capture(self):
        self.timer.stop()
        self._show_roi_overlay()
        self.log_msg("Capture stopped. ROI remains set.")
        self.update_ui()

    def open_folder(self):
        os.startfile(self.output_dir)

    def capture(self):
        if not self.region:
            return

        roi_top_left = QPoint(self.region.x, self.region.y)
        screen = QGuiApplication.screenAt(roi_top_left) or QGuiApplication.primaryScreen()
        if screen is None:
            self.log_msg("ERROR: No screen found.")
            return

        geom = screen.geometry()  # DIPs
        dpr = float(screen.devicePixelRatio())

        local_x = self.region.x - geom.x()
        local_y = self.region.y - geom.y()

        px_x = int(round(local_x * dpr))
        px_y = int(round(local_y * dpr))
        px_w = int(round(self.region.w * dpr))
        px_h = int(round(self.region.h * dpr))

        overlay_was_visible = self._roi_overlay is not None and self._roi_overlay.isVisible()
        if overlay_was_visible:
            self._hide_roi_overlay()
            QApplication.processEvents()

        pixmap = screen.grabWindow(0, px_x, px_y, px_w, px_h)

        if overlay_was_visible:
            self._show_roi_overlay()
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
        if self._roi_overlay is not None:
            self._roi_overlay.close()
            self._roi_overlay = None
        super().closeEvent(event)


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
