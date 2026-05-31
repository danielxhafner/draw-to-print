from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".draw_to_printer" / "config.json"

# Standard paper sizes in mm (width x height, portrait)
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "A0": (841.0, 1189.0),
    "A1": (594.0, 841.0),
    "A2": (420.0, 594.0),
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "B0": (1000.0, 1414.0),
    "B1": (707.0, 1000.0),
    "B2": (500.0, 707.0),
    "B3": (353.0, 500.0),
    "B4": (250.0, 353.0),
    "B5": (176.0, 250.0),
    "Letter": (215.9, 279.4),
    "Custom": (210.0, 297.0),
}


@dataclass
class Config:
    # PDF Setup
    paper_preset: str = "A4"
    pdf_width_mm: float = 210.0
    pdf_height_mm: float = 297.0
    dpi: int = 300
    background_color: str = "#ffffff"
    transparent_background: bool = False

    # Fitting Options
    fitting_mode: str = "proportional"   # "proportional" | "scale_to_format"
    device_width_cm: float = 13.0        # physical input device width
    device_height_cm: float = 8.0        # physical input device height
    unlimited_canvas: bool = False       # warp-and-track infinite canvas mode

    # Line Configuration
    line_thickness_pt: float = 1.0
    line_color: str = "#000000"
    thickness_timing: str = "after"      # "before" | "after" fitting

    # Vector Look
    smoothness: int = 50                 # 0 = precise, 100 = very smooth

    # Number of Lines
    default_line_count: int = 1          # strokes before print triggers

    # Archive
    archive_folder: str = str(Path.home() / "draw_to_printer_archive")

    # Mouse / Input
    input_device: str = ""               # empty = system default

    # Printing
    printer_name: str = ""               # empty = system default
    save_pdf_only: bool = False           # skip sending to printer


def load_config() -> Config:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = Config()
            for key, value in data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)
            return cfg
        except Exception:
            pass
    return Config()


def save_config(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)

