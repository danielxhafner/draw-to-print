from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import List, Tuple

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QKeySequence

from config_manager import Config, load_config, save_config
from canvas_widget import CanvasWidget
from config_dialog import ConfigDialog
from pdf_builder import build_pdf
from printer_manager import print_file
from archive_manager import save_to_archive

Stroke = List[Tuple[float, float]]


class _PrintWorker(QObject):
    """Runs the PDF build + print + archive pipeline off the main thread."""

    finished = pyqtSignal(str)   # archive path or error message
    error = pyqtSignal(str)

    def __init__(self, strokes: List[Stroke], cfg: Config, canvas_w: float, canvas_h: float):
        super().__init__()
        self._strokes = strokes
        self._cfg = cfg
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h

    def run(self):
        try:
            pdf_path = build_pdf(self._strokes, self._cfg, self._canvas_w, self._canvas_h)
            if not self._cfg.save_pdf_only:
                print_file(pdf_path, self._cfg.printer_name)
            archive_path = save_to_archive(pdf_path, self._cfg)
            # Clean up temp file
            try:
                pdf_path.unlink()
            except OSError:
                pass
            self.finished.emit(str(archive_path))
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("draw_to_printer")

        self._canvas = CanvasWidget(cfg, on_print_cycle=self._on_print_cycle)
        self.setCentralWidget(self._canvas)

        self._print_thread: QThread | None = None
        self._worker: _PrintWorker | None = None

        self._setup_shortcut()
        self.showFullScreen()

    def _setup_shortcut(self):
        from PyQt5.QtWidgets import QShortcut
        sc = QShortcut(QKeySequence("S"), self)
        sc.activated.connect(self._open_config)

        pref_shortcut = QShortcut(QKeySequence(QKeySequence.Preferences), self)
        pref_shortcut.activated.connect(self._open_config)

    def _open_config(self):
        dlg = ConfigDialog(self.cfg, parent=self)
        if dlg.exec_() == ConfigDialog.Accepted:
            self.cfg = dlg.get_config()
            self._canvas.reload_config(self.cfg)

    def _on_print_cycle(self, strokes: List[Stroke], canvas_w: float, canvas_h: float):
        """Called from canvas when stroke target is reached. Runs pipeline in background."""
        if self._print_thread and self._print_thread.isRunning():
            # Previous job still running — queue is not supported; drop silently
            return
        self._canvas.show_status("Printing…")

        self._worker = _PrintWorker(strokes, self.cfg, canvas_w, canvas_h)
        self._print_thread = QThread()
        self._worker.moveToThread(self._print_thread)

        self._print_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_print_done)
        self._worker.error.connect(self._on_print_error)
        self._worker.finished.connect(self._print_thread.quit)
        self._worker.error.connect(self._print_thread.quit)
        self._print_thread.finished.connect(self._cleanup_thread)

        self._print_thread.start()

    def _on_print_done(self, archive_path: str):
        name = Path(archive_path).name
        status_msg = "Saved" if self.cfg.save_pdf_only else "Saved & printed"
        self._canvas.show_status(f"{status_msg}  →  {name}")

    def _on_print_error(self, msg: str):
        self._canvas.show_status(f"Error: {msg}")

    def _cleanup_thread(self):
        self._print_thread = None
        self._worker = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or (
            event.key() == Qt.Key_Q and event.modifiers() & Qt.ControlModifier
        ):
            self.close()
        else:
            super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("draw_to_printer")
    app.setDoubleClickInterval(250)  # Speed up double-click recognition (default: 400ms)

    cfg = load_config()

    # Ensure archive folder exists
    Path(cfg.archive_folder).mkdir(parents=True, exist_ok=True)

    win = MainWindow(cfg)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
