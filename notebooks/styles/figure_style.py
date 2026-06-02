"""Shared plotting style utilities for figure notebooks."""

from pathlib import Path

import matplotlib.pyplot as plt

PALETTE = {
    "light_blue": "#56B4E9",
    "dark_blue": "#0072B2",
    "light_orange": "#E69F00",
    "dark_orange": "#D55E00",
    "teal": "#009E73",
    "yellow": "#F0E442",
    "purple": "#CC79A7",
    "black": "#000000",
}


def apply_photeros_style(style_path: str | Path) -> None:
    """Apply the project-level matplotlib style from a .mplstyle file."""
    plt.style.use(str(style_path))


def get_palette() -> dict:
    """Return a copy of the shared color palette."""
    return PALETTE.copy()
