# draw to print

A fullscreen drawing utility that converts hand-drawn strokes into vector PDF output and sends it to a printer or archive without any dialogs or confirmation windows.

Find out how far you can move your Bluetooth mouse away from your computer while drawing, or simply streamline and accelerate your drawing process.

![bildbeschreibung](./assets/screen3.png)

## Setup 

### Requirements
- Python 3.x
- `PyQt5`
- `reportlab`
- A working CUPS environment with `lp` and `lpstat` available (macOS/Linux)

### Install dependencies

Create or activate your Python environment, then install dependencies:

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

## Overview

`draw_to_printer` captures freehand strokes, converts them into a vector PDF, and either prints the PDF or saves it to an archive.

### Key features

- Fullscreen drawing canvas built with PyQt5
- Configurable print cycle triggered by stroke count 1-100
- Vector PDF generation with smoothing and fitting logic
- PDF printing with CUPS via `lp`
- `save_pdf_only` mode to skip printing and only save the PDF
- Automatic archive copy of every generated PDF using timestamped filenames
- Persistent configuration in `~/.draw_to_printer/config.json`

## New setup titles and functions

### Setup titles
- `Print Format`
- `Input`
- `Scaling`
- `Vector`
- `Number of Strokes`
- `Archive Folder`

![bildbeschreibung](./assets/screen1.png)
![bildbeschreibung](./assets/screen2.png)

### Main functions and modules

- `draw_to_printer.py`
  - `MainWindow` - main application window and print workflow
  - `_on_print_done()` - updates status text after PDF generation
  - `_on_print_error()` - shows errors from the print/archival pipeline

- `config_manager.py`
  - `Config` dataclass - holds all runtime settings
  - `load_config()` - loads settings from `~/.draw_to_printer/config.json`
  - `save_config()` - writes settings back to disk

- `pdf_builder.py`
  - `build_pdf()` - converts strokes into a PDF file
  - PDF smoothing helpers: `_rdp_simplify()`, `_chaikin()`, `_smoothness_to_iterations()`

- `printer_manager.py`
  - `list_printers()` - finds available printers via `lpstat`
  - `get_default_printer()` - returns the system default printer
  - `print_file()` - sends a PDF to a printer via `lp`

- `archive_manager.py`
  - `save_to_archive()` - copies PDFs to the configured archive folder with a timestamped filename

## How it works

1. Draw with the left mouse button.
2. Strokes are collected until the configured threshold is reached.
3. The app builds a PDF from the strokes.
4. If `save_pdf_only` is disabled, the PDF is sent to the selected printer.
5. The PDF is archived to the configured archive folder.
6. The UI status shows `Saved` or `Saved & printed` depending on the current mode.

## Controls

- Left mouse button: draw strokes
- Right mouse button: increment the line/print target count
- Right double-click: reset the target count to 1
- `S` or `command+,`key: open the settings dialog
- `Escape` or `Ctrl+Q`: quit the application

## Settings

Open the configuration window with `S` or `command+,` to adjust:

- paper size and custom PDF dimensions
- DPI and background color
- fitting mode (`proportional` or `scale_to_format`)
- input device dimensions and unlimited canvas mode
- Vector contour, color, and smoothing
- number of strokes required for a print cycle (Works on a limited canvas only)
- archive folder and printer selection
- `save_pdf_only` to skip printing and only save PDFs

## File locations

- Main entry point: `draw_to_printer.py`
- Startup wrapper: `start.sh`
- Config file: `~/.draw_to_printer/config.json`
- Archived PDFs: default `~/draw_to_printer_archive`

## Notes

- If no printer is configured, the system default printer is used.
- The app depends on CUPS commands, so ensure `lp` and `lpstat` are available on your PATH.
- The archive folder is created automatically when needed.

