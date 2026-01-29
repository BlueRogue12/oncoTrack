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
    # Changed from TimedSnips -> OncoTrackSnaps for better integration naming
    docs = Path(os.path.expanduser("~/Documents"))
    out = docs / "OncoTrackSnaps"
    out.mkdir(exist_ok=True)
    return out


class ScreenSelector(QWidget):
    """
    Top-level fullscreen overlay over the virtual desktop (all monitors).
    Emits (rect_local, overlay_global_top_left) so we can compute global coords.
    """
    selected = Signal(QRect, QPoint)   # (rect_local, overlay_top_left_global)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None)  # IMPORTANT: no parent => not confined to main window

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

        self._origin: QPoint | None = None
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)
        self._rubber.hide()

        self._virtual = QGuiApplication.primaryScreen().virtualGeometry()
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        painter.setPen(QPen(QColor(255, 255, 255, 230)))
        painter.drawText(20, 35, "Drag to define ROI. Press Esc to cancel.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.stop()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.position().toPoint()
        self._rubber.setGeometry(QRect(self._origin, QPoint()))
        self._rubber.show()

    def mouseMoveEvent(self, event):
        if self._origin is None:
            return
        current = event.position().toPoint()
        self._rubber.setGeometry(QRect(self._origin, current).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._origin is None:
            return

        rect_local = self._rubber.geometry().normalized()
        self._origin = None

        # Prevent accidental clicks (tiny selection)
        if rect_local.width() < 5 or rect_local.height() < 5:
            self.cancelled.emit()
            self.stop()
            return

        self.selected.emit(rect_local, self._virtual.topLeft())
        self.stop()


class ScreenshotApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OncoTrack: Frame Capture")
        self.resize(560, 320)

        self.output_dir = get_output_folder()
        self.region: CaptureRegion | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture)

        self._selector: ScreenSelector | None = None

        self.build_ui()
        self.update_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Subtle hierarchy styling
        label_style = "color: #666;"
        status_style = "font-weight: 600;"

        self.folder_label = QLabel(f"Save folder: {self.output_dir}")
        self.folder_label.setStyleSheet(label_style)
        layout.addWidget(self.folder_label)

        self.region_label = QLabel("ROI: (none)")
        self.region_label.setStyleSheet(label_style)
        layout.addWidget(self.region_label)

        # Timer picker: Minutes + Seconds
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Capture interval:"))

        self.minutes_combo = QComboBox()
        self.seconds_combo = QComboBox()

        for m in range(0, 60):
            self.minutes_combo.addItem(f"{m:02d}", m)
        for s in range(0, 60):
            self.seconds_combo.addItem(f"{s:02d}", s)

        # Default 00:20
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
        self.select_btn = QPushButton("Define ROI")
        self.play_btn = QPushButton("Start Capture")
        self.stop_btn = QPushButton("Stop Capture")
        self.open_btn = QPushButton("Open Folder")

        self.select_btn.clicked.connect(self.select_area)
        self.play_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)
        self.open_btn.clicked.connect(self.open_folder)

        btn_row.addWidget(self.select_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.open_btn)
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

        self.status.setText("Capture status: Capturing" if running else "Capture status: Idle")

    def interval_ms(self) -> int:
        minutes = int(self.minutes_combo.currentData())
        seconds = int(self.seconds_combo.currentData())
        total_seconds = minutes * 60 + seconds
        return total_seconds * 1000

    def interval_label(self) -> str:
        minutes = int(self.minutes_combo.currentData())
        seconds = int(self.seconds_combo.currentData())
        return f"{minutes:02d}:{seconds:02d}"

    def select_area(self):
        if self.timer.isActive():
            return

        self.log_msg("Define ROI by dragging. Press Esc to cancel.")

        self._selector = ScreenSelector()
        self._selector.selected.connect(self.on_selected)
        self._selector.cancelled.connect(lambda: self.log_msg("ROI selection cancelled."))
        self._selector.start()

    def on_selected(self, rect_local: QRect, overlay_top_left: QPoint):
        # Convert overlay-local coords to global desktop coords
        global_x = overlay_top_left.x() + rect_local.x()
        global_y = overlay_top_left.y() + rect_local.y()

        self.region = CaptureRegion(global_x, global_y, rect_local.width(), rect_local.height())

        self.region_label.setText(
            f"ROI: x={self.region.x}, y={self.region.y}, w={self.region.w}, h={self.region.h}"
        )
        self.log_msg("ROI set.")
        self.update_ui()

    def start_capture(self):
        if not self.region:
            QMessageBox.warning(self, "No ROI", "Define an ROI first.")
            return

        ms = self.interval_ms()
        if ms <= 0:
            QMessageBox.warning(self, "Invalid interval", "Choose a non-zero capture interval.")
            return

        self.capture()  # immediate first capture
        self.timer.start(ms)
        self.log_msg(f"Capture started (interval {self.interval_label()} mm:ss). ROI locked until Stop.")
        self.update_ui()

    def stop_capture(self):
        self.timer.stop()
        self.log_msg("Capture stopped. Press Start Capture to resume with the same ROI.")
        self.update_ui()

    def open_folder(self):
        os.startfile(self.output_dir)

    def capture(self):
        """
        DPI FIX:
        Do NOT multiply by devicePixelRatio().
        The selection coordinates are already in the coordinate space that grabWindow expects
        for desktop capture in typical Windows configurations; multiplying causes oversizing.
        """
        if not self.region:
            return

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.log_msg("ERROR: No primary screen found.")
            return

        # Use the selected region directly (no DPR scaling)
        x = int(self.region.x)
        y = int(self.region.y)
        w = int(self.region.w)
        h = int(self.region.h)

        pixmap = screen.grabWindow(0, x, y, w, h)
        if pixmap.isNull():
            self.log_msg("ERROR: Capture failed (pixmap is null).")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.output_dir / f"frame_{ts}.png"
        pixmap.save(str(path), "PNG")
        self.log_msg(f"Saved {path.name}")


def main():
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
