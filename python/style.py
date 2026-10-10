"""Shared chart style: one accent blue plus greys, one axis per chart, light gridlines, titles that state the finding."""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"
IMG.mkdir(parents=True, exist_ok=True)

INK, MUTED, GRID = "#1F2937", "#6B7280", "#E5E7EB"
ACCENT, ACCENT_MID, ACCENT_LIGHT, GREY = "#1D4E89", "#5B84B1", "#C9D6E6", "#9CA3AF"
SEQ = LinearSegmentedColormap.from_list("mono_blue", ["#F3F6FA", "#C9D6E6", "#5B84B1", "#1D4E89"])


def apply():
    mpl.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 200, "figure.facecolor": "white", "axes.facecolor": "white",
        "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.labelcolor": MUTED,
        "axes.edgecolor": GRID, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.axisbelow": True, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "legend.frameon": False, "axes.titlepad": 12})


def save(fig, name):
    fig.savefig(IMG / name, bbox_inches="tight", facecolor="white")
    return IMG / name


def hbar_labels(ax, bars, fmt="{:.1f}%", pad=0.6, color=INK):
    for b in bars:
        ax.text(b.get_width() + pad, b.get_y() + b.get_height() / 2, fmt.format(b.get_width()),
                va="center", ha="left", fontsize=9, color=color)
