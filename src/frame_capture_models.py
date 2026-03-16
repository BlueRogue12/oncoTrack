from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


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
# Coordinate conversion helpers
# ----------------------------

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