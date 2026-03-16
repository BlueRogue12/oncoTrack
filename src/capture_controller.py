from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import QObject, QTimer, QPoint
from PySide6.QtGui import QGuiApplication

from src.frame_capture_models import (
    CaptureRegion,
    Calibration,
    OriginConfig,
    AxisConvention,
    get_output_folder,
)


class CaptureController(QObject):
    """
    Handles frame capture logic independent of UI.
    """

    def __init__(self):
        super().__init__()

        self.output_dir = get_output_folder()

        self.region: Optional[CaptureRegion] = None
        self.calibration = Calibration()
        self.origin = OriginConfig()
        self.axis_conv = AxisConvention()

        self.timer = QTimer()
        self.timer.timeout.connect(self.capture)

        # Optional hooks set by the UI layer
        self.before_capture_hook: Optional[Callable[[], None]] = None
        self.after_capture_hook: Optional[Callable[[], None]] = None
        self.on_frame_saved: Optional[Callable[[Path], None]] = None
        self.on_capture_error: Optional[Callable[[str], None]] = None

    def set_region(self, region: Optional[CaptureRegion]):
        self.region = region

    def start_capture(self, interval_ms: int):
        if not self.region:
            return

        self.capture()
        self.timer.start(interval_ms)

    def stop_capture(self):
        self.timer.stop()

    def is_running(self) -> bool:
        return self.timer.isActive()

    def capture(self):
        if not self.region:
            return

        roi_top_left = QPoint(self.region.x, self.region.y)
        screen = QGuiApplication.screenAt(roi_top_left) or QGuiApplication.primaryScreen()

        if not screen:
            if self.on_capture_error:
                self.on_capture_error("ERROR: No screen found.")
            return

        geom = screen.geometry()

        # Qt expects logical pixels here
        log_x = self.region.x - geom.x()
        log_y = self.region.y - geom.y()

        if self.before_capture_hook:
            self.before_capture_hook()

        pixmap = screen.grabWindow(
            0,
            log_x,
            log_y,
            self.region.w,
            self.region.h,
        )

        if self.after_capture_hook:
            self.after_capture_hook()

        if pixmap.isNull():
            if self.on_capture_error:
                self.on_capture_error("ERROR: Capture failed (pixmap is null).")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.output_dir / f"frame_{ts}.png"
        pixmap.save(str(path), "PNG")

        if self.on_frame_saved:
            self.on_frame_saved(path)