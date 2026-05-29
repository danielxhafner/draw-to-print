# draw_to_printer

A fullscreen drawing utility that converts hand-drawn strokes into vector PDF output and sends the result to a printer or archive.

## Getting Started

### Requirements
- Python 3.x
- `PyQt5`
- `reportlab`
- A working CUPS environment with `lp` and `lpstat` available (macOS/Linux)

### Install dependencies

Use your virtual environment or global Python environment:

```sh
python -m pip install PyQt5 reportlab
```

If you use the built-in `.venv`, activate it first:

```sh
source .venv/bin/activate
```

### Run the program

From the project root:

```sh
./start.sh
```

This launches the application using the Python interpreter from `.venv` and runs `draw_to_printer.py`.

## Program Overview

`draw_to_printer` is designed to capture strokes, convert them into a printable PDF, and optionally print immediately.

### Main functionality

- Fullscreen drawing canvas using PyQt5
- Automatic print cycle after a configurable number of strokes
- Vector PDF generation with smoothing and fitting
- Printing via CUPS (`lp`) or saving PDF only
- Archive copy of every generated PDF with timestamped filenames
- Persistent settings stored in `~/.draw_to_printer/config.json`

### What happens when you draw

1. Draw strokes with the left mouse button.
2. Each completed stroke is stored.
3. After the configured number of strokes is reached, the app:
   - builds a PDF from the strokes,
   - sends the PDF to the selected printer (unless `save_pdf_only` is enabled),
   - archives a copy in the configured archive folder,
   - clears the current drawing session.

## Controls

- Left mouse button: draw strokes
- Right mouse button: increment the line/print target count
- Right double-click: reset target count to 1
- `S` key: open the settings dialog
- `Escape` or `Ctrl+Q`: quit the application

## Settings

Open the configuration window with `S` to adjust:

- paper size and custom PDF dimensions
- DPI and background color
- fitting mode (`proportional` or `scale_to_format`)
- input device dimensions and unlimited canvas mode
- line thickness, color, and smoothing
- number of strokes required for a print cycle
- archive folder and printer selection
- `save_pdf_only` to skip actual printing

## File locations

- Main entry point: `draw_to_printer.py`
- Startup wrapper: `start.sh`
- Config file: `~/.draw_to_printer/config.json`
- Archived PDFs: default `~/draw_to_printer_archive`

## Notes

- If no printer is configured, the system default is used.
- The app relies on CUPS commands, so ensure `lp` and `lpstat` are installed and available in your PATH.
- The archive folder is created automatically on first run.
