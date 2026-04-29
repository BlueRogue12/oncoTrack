"""
Generate paper figures from tracking database:
  1. Trajectory plot — all cell paths over time
  2. Velocity distribution histogram — step velocities across all cells
"""

import sqlite3
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "tracking.db"
OUT_DIR = Path(__file__).parent.parent / "output" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Figure 1: Trajectory Plot ────────────────────────────────────────────────

def plot_trajectories():
    conn = get_connection()
    cur = conn.cursor()

    # Get all cells that have at least 5 points (filter out noise/short tracks)
    cur.execute("""
        SELECT cell_id, COUNT(*) as n
        FROM points
        GROUP BY cell_id
        HAVING n >= 5
        ORDER BY cell_id
    """)
    cells = [row["cell_id"] for row in cur.fetchall()]

    # Get image dimensions for axis limits
    cur.execute("SELECT MAX(x) as mx, MAX(y) as my FROM points")
    row = cur.fetchone()
    max_x, max_y = row["mx"], row["my"]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_facecolor("#1a1a1a")
    fig.patch.set_facecolor("#1a1a1a")

    colors = cm.colormaps["tab20"].resampled(len(cells))

    for idx, cell_id in enumerate(cells):
        cur.execute("""
            SELECT x, y, frame_index
            FROM points
            WHERE cell_id = ?
            ORDER BY frame_index
        """, (cell_id,))
        pts = cur.fetchall()
        if len(pts) < 2:
            continue

        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]

        color = colors(idx)
        ax.plot(xs, ys, color=color, linewidth=0.9, alpha=0.75)
        # Mark start and end
        ax.plot(xs[0], ys[0], "o", color=color, markersize=3, alpha=0.9)
        ax.plot(xs[-1], ys[-1], "s", color=color, markersize=3, alpha=0.9)

    ax.set_xlim(0, max_x * 1.05)
    ax.set_ylim(max_y * 1.05, 0)  # invert Y to match image coordinates
    ax.set_xlabel("X Position (pixels)", color="white", fontsize=12)
    ax.set_ylabel("Y Position (pixels)", color="white", fontsize=12)
    ax.set_title("Reconstructed Particle Trajectories", color="white", fontsize=14, pad=12)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#555555")

    # Legend entries
    ax.plot([], [], "o-", color="white", linewidth=0.9, markersize=3, label="Trajectory (circle = start, square = end)")
    ax.legend(facecolor="#2a2a2a", labelcolor="white", fontsize=9, loc="upper right")

    out_path = OUT_DIR / "trajectory_plot.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {out_path}")
    conn.close()


# ─── Figure 2: Velocity Distribution Histogram ────────────────────────────────

def plot_velocity_histogram():
    conn = get_connection()
    cur = conn.cursor()

    # Try stored velocities first, fall back to computing from points
    cur.execute("SELECT velocity FROM track_step_velocities WHERE velocity > 0")
    velocities = [row["velocity"] for row in cur.fetchall()]

    if not velocities:
        print("No stored velocities found — computing from points...")
        cur.execute("""
            SELECT cell_id, x, y, frame_index
            FROM points
            ORDER BY cell_id, frame_index
        """)
        rows = cur.fetchall()

        from itertools import groupby
        velocities = []
        for cell_id, pts in groupby(rows, key=lambda r: r["cell_id"]):
            pts = list(pts)
            for a, b in zip(pts, pts[1:]):
                dt = b["frame_index"] - a["frame_index"]
                if dt == 0:
                    continue
                dx = b["x"] - a["x"]
                dy = b["y"] - a["y"]
                v = ((dx**2 + dy**2) ** 0.5) / dt
                if v > 0:
                    velocities.append(v)

    if not velocities:
        print("No velocity data available.")
        conn.close()
        return

    velocities = np.array(velocities)
    avg_vels = None

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.set_facecolor("#1a1a1a")
    fig.patch.set_facecolor("#1a1a1a")

    n, bins, _ = ax.hist(
        velocities, bins=40, color="#4a90d9", edgecolor="#2a2a2a",
        alpha=0.85, label=f"Step velocities (n={len(velocities)})"
    )

    # Mark mean and median
    mean_v = np.mean(velocities)
    median_v = np.median(velocities)
    ax.axvline(mean_v, color="#ff6b6b", linewidth=1.8, linestyle="--", label=f"Mean: {mean_v:.2f} px/frame")
    ax.axvline(median_v, color="#ffd93d", linewidth=1.8, linestyle=":", label=f"Median: {median_v:.2f} px/frame")

    ax.set_xlabel("Velocity (pixels/frame)", color="white", fontsize=12)
    ax.set_ylabel("Frequency", color="white", fontsize=12)
    ax.set_title("Step Velocity Distribution Across All Tracked Particles", color="white", fontsize=14, pad=12)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#555555")

    ax.legend(facecolor="#2a2a2a", labelcolor="white", fontsize=10)

    # Stats annotation
    stats_text = (
        f"Min:  {np.min(velocities):.2f}\n"
        f"Max:  {np.max(velocities):.2f}\n"
        f"Std:   {np.std(velocities):.2f}"
    )
    ax.text(
        0.97, 0.95, stats_text,
        transform=ax.transAxes, fontsize=9, color="white",
        verticalalignment="top", horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="#2a2a2a", alpha=0.8)
    )

    out_path = OUT_DIR / "velocity_histogram.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {out_path}")
    conn.close()


if __name__ == "__main__":
    print("Generating figures from tracking database...")
    plot_trajectories()
    plot_velocity_histogram()
    print("Done. Figures saved to output/figures/")
