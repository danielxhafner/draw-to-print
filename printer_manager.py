from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List


def list_printers() -> List[str]:
    """Return available printer names via CUPS lpstat (macOS + Linux)."""
    try:
        result = subprocess.run(
            ["lpstat", "-a"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        printers: List[str] = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts:
                printers.append(parts[0])
        return printers
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def get_default_printer() -> str:
    """Return the system default printer name, or empty string."""
    try:
        result = subprocess.run(
            ["lpstat", "-d"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Output: "system default destination: PrinterName"
        line = result.stdout.strip()
        if ":" in line:
            return line.split(":", 1)[1].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def print_file(pdf_path: Path, printer_name: str) -> bool:
    """
    Send pdf_path to printer_name silently via CUPS lp.
    Returns True on success, False on failure.
    """
    cmd = ["lp"]
    if printer_name:
        cmd += ["-d", printer_name]
    cmd.append(str(pdf_path))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
