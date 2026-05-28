from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple, Callable

from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt5.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QFont, QFontMetrics
)
from PyQt5.QtWidgets import QWidget, QApplication

from config_manager import Config

Point = Tuple[float, float]
Stroke = List[Point]


class CanvasWidget(QWidget):
    def __init__(self, cfg: Config, on_print_cycle: Callable[[List[Stroke], float, float], None]):
        super().__init__()
        self.cfg = cfg
        self.on_print_cycle = on_print_cycle

        self._session_strokes: List[Stroke] = []
        self._current_stroke: Optional[Stroke] = None
        self._drawing = False
        self._hud_message = ""
        self._hud_timer = QTimer(self)
        self._hud_timer.setSingleShot(True)
        self._hud_timer.timeout.connect(self._clear_hud_message)

        self.setWindowTitle("draw_to_printer")
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    # ------------------------------------------------------------------ #
    #  Mouse Events                                                         #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = True
            pt = self._capture_point(event)
            self._current_stroke = [pt]
        elif event.button() == Qt.RightButton:
            self._increment_target()

    def mouseMoveEvent(self, event):
        if self._drawing and self._current_stroke is not None:
            pt = self._capture_point(event)
            self._current_stroke.append(pt)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            if self._current_stroke and len(self._current_stroke) >= 2:
                self._session_strokes.append(self._current_stroke)
            self._current_stroke = None
            self.update()

            # Check if target count reached
            target = self.cfg.default_line_count
            if len(self._session_strokes) >= target:
                self._trigger_print_cycle()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.RightButton:
            self._reset_target()

    def _capture_point(self, event) -> Point:
        """Return (x, y) — global coords for scale_to_format, local for proportional."""
        if self.cfg.fitting_mode == "scale_to_format":
            gp = event.globalPos()
            return (float(gp.x()), float(gp.y()))
        else:
            return (float(event.x()), float(event.y()))

    # ------------------------------------------------------------------ #
    #  Right-click: increment target count                                  #
    # ------------------------------------------------------------------ #

    def _increment_target(self):
        current = self.cfg.default_line_count
        current = (current % 100) + 1
        self.cfg.default_line_count = current
        # Persist immediately
        from config_manager import save_config
        save_config(self.cfg)
        self._show_hud_message(f"Lines per print set to {current}")

    def _reset_target(self):
        self.cfg.default_line_count = 1
        # Persist immediately
        from config_manager import save_config
        save_config(self.cfg)
        self._show_hud_message("Lines per print reset to 1")

    # ------------------------------------------------------------------ #
    #  Print Cycle                                                          #
    # ------------------------------------------------------------------ #

    def _trigger_print_cycle(self):
        strokes = list(self._session_strokes)
        self._session_strokes = []
        self.update()
        # Pass canvas dimensions so fitting knows the coordinate space
        self.on_print_cycle(strokes, float(self.width()), float(self.height()))

    # ------------------------------------------------------------------ #
    #  HUD                                                                  #
    # ------------------------------------------------------------------ #

    def _show_hud_message(self, msg: str, duration_ms: int = 2000):
        self._hud_message = msg
        self._hud_timer.start(duration_ms)
        self.update()

    def _clear_hud_message(self):
        self._hud_message = ""
        self.update()

    def show_status(self, msg: str):
        """Called externally to display a transient status message."""
        self._show_hud_message(msg, 3000)

    # ------------------------------------------------------------------ #
    #  Painting                                                             #
    # ------------------------------------------------------------------ #

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        bg = QColor(self.cfg.background_color)
        painter.fillRect(self.rect(), bg)

        line_color = QColor(self.cfg.line_color)
        pen = QPen(line_color, self.cfg.line_thickness_pt, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        # Draw all committed strokes
        for stroke in self._session_strokes:
            self._draw_stroke(painter, stroke)

        # Draw stroke in progress
        if self._current_stroke and len(self._current_stroke) >= 2:
            self._draw_stroke(painter, self._current_stroke)

        # HUD overlay
        self._draw_hud(painter)

    def _draw_stroke(self, painter: QPainter, stroke: Stroke):
        if len(stroke) < 2:
            return

        if self.cfg.fitting_mode == "scale_to_format":
            # Points are global coords; translate to widget-local for display
            pts = self._global_to_local(stroke)
        else:
            pts = stroke

        # Apply the same RDP + Chaikin smoothing used in PDF output
        from pdf_builder import _chaikin, _smoothness_to_iterations, _rdp_simplify, _smoothness_to_epsilon
        eps = _smoothness_to_epsilon(self.cfg.smoothness, pts)
        if eps > 0:
            pts = _rdp_simplify(pts, eps)
        iters = _smoothness_to_iterations(self.cfg.smoothness)
        pts = _chaikin(pts, iters)

        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        painter.drawPath(path)

    def _global_to_local(self, stroke: Stroke) -> Stroke:
        origin = self.mapToGlobal(self.rect().topLeft())
        ox, oy = origin.x(), origin.y()
        return [(x - ox, y - oy) for x, y in stroke]

    def _draw_hud(self, painter: QPainter):
        target = self.cfg.default_line_count
        done = len(self._session_strokes)
        counter_text = f"Strokes: {done} / {target}"

        # Choose contrasting colour vs background
        bg = QColor(self.cfg.background_color)
        brightness = bg.red() * 0.299 + bg.green() * 0.587 + bg.blue() * 0.114
        hud_color = QColor("#000000") if brightness > 128 else QColor("#ffffff")

        font = QFont("Monospace", 13)
        font.setStyleHint(QFont.TypeWriter)
        painter.setFont(font)
        painter.setPen(QPen(hud_color))

        margin = 18
        fm = QFontMetrics(font)

        # Counter — top left
        painter.drawText(margin, margin + fm.ascent(), counter_text)

        # Transient HUD message — bottom center
        if self._hud_message:
            w = fm.horizontalAdvance(self._hud_message)
            x = (self.width() - w) // 2
            y = self.height() - margin
            painter.drawText(x, y, self._hud_message)

    # ------------------------------------------------------------------ #
    #  Config reload                                                        #
    # ------------------------------------------------------------------ #

    def reload_config(self, cfg: Config):
        self.cfg = cfg
        self.update()
