"""
Generate a sequential flow diagram for the OncoTrack system.
Boxes connected top-to-bottom with arrows, dark background, dark text in boxes.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

STEPS = [
    "Upload Microscopy Video",
    "Preprocess Frames",
    "Detect & Track Cells",
    "Generate Trajectories",
    "Compute Migration Metrics",
    "Export Results",
]

BOX_W = 2.8
BOX_H = 0.55
GAP = 0.38           # vertical gap between boxes
ARROW_H = GAP        # arrow spans the gap
X_CENTER = 0.0
FIG_W = 5.5
FIG_H = 9.0

# y positions (top of each box), counting downward in data coords
# We'll use a simple coord system where y increases upward but we place
# boxes at decreasing y values.

N = len(STEPS)
total_h = N * BOX_H + (N - 1) * GAP
y_top = total_h / 2  # topmost box top edge

box_tops = [y_top - i * (BOX_H + GAP) for i in range(N)]
box_bottoms = [t - BOX_H for t in box_tops]
box_centers_y = [(t + b) / 2 for t, b in zip(box_tops, box_bottoms)]

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor("#1e1e2e")
ax.set_facecolor("#1e1e2e")

ax.set_xlim(-FIG_W / 2, FIG_W / 2)
ax.set_ylim(box_bottoms[-1] - 0.4, box_tops[0] + 0.4)
ax.set_aspect("equal")
ax.axis("off")

# Title
ax.text(
    X_CENTER, box_tops[0] + 0.28,
    "OncoTrack System",
    ha="center", va="center",
    fontsize=13, fontweight="bold", color="white",
    fontfamily="sans-serif",
)

# Draw arrows first (so boxes render on top)
for i in range(N - 1):
    arrow_x = X_CENTER
    arrow_y_start = box_bottoms[i] - 0.02
    arrow_y_end = box_tops[i + 1] + 0.02

    ax.annotate(
        "",
        xy=(arrow_x, arrow_y_end),
        xytext=(arrow_x, arrow_y_start),
        arrowprops=dict(
            arrowstyle="-|>",
            color="#9db4cc",
            lw=1.8,
            mutation_scale=14,
        ),
    )

# Draw boxes
BOX_COLOR = "#e8dfd0"
TEXT_COLOR = "#1a1a2e"
BORDER_COLOR = "#a89880"

for i, (label, cy) in enumerate(zip(STEPS, box_centers_y)):
    x0 = X_CENTER - BOX_W / 2
    y0 = cy - BOX_H / 2

    box = FancyBboxPatch(
        (x0, y0), BOX_W, BOX_H,
        boxstyle="round,pad=0.06",
        facecolor=BOX_COLOR,
        edgecolor=BORDER_COLOR,
        linewidth=1.4,
        zorder=3,
    )
    ax.add_patch(box)

    ax.text(
        X_CENTER, cy,
        label,
        ha="center", va="center",
        fontsize=10.5, fontweight="semibold",
        color=TEXT_COLOR,
        fontfamily="sans-serif",
        zorder=4,
    )

out_path = "pipeline_flow.png"
plt.savefig(
    out_path, dpi=180, bbox_inches="tight",
    facecolor=fig.get_facecolor(),
)
plt.close()
print(f"Saved: {out_path}")
