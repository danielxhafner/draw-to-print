from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from config_manager import Config


def save_to_archive(pdf_path: Path, cfg: Config) -> Path:
    """
    Copy pdf_path to the configured archive folder with a timestamp filename.
    Returns the destination path.
    """
    dest_dir = Path(cfg.archive_folder)
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{timestamp}.pdf"

    # Ensure uniqueness in the unlikely case of a collision
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{timestamp}_{counter}.pdf"
        counter += 1

    shutil.copy2(str(pdf_path), str(dest))
    return dest
