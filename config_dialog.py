from __future__ import annotations

import copy
from pathlib import Path
from typing import List

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QPainterPath
)
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QRadioButton, QButtonGroup, QFileDialog, QSlider, QColorDialog,
    QGroupBox, QSizePolicy, QDialogButtonBox, QLineEdit, QFormLayout,
    QFrame, QCheckBox,
)
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrinterInfo

from config_manager import Config, PAPER_SIZES_MM, save_config


class _ColorButton(QPushButton):
    """A button that shows the current color and opens a color picker."""

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color_hex)
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self):
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = "#000000" if luma > 128 else "#ffffff"
        self.setStyleSheet(
            f"background-color: {self._color.name()}; color: {text_color}; "
            "border: 1px solid #888; padding: 4px 12px; border-radius: 4px;"
        )
        self.setText(self._color.name().upper())

    def _pick(self):
        col = QColorDialog.getColor(self._color, self, "Choose colour")
        if col.isValid():
            self._color = col
            self._refresh()

    def color_hex(self) -> str:
        return self._color.name()


class _FittingPreview(QWidget):
    """Live mini-diagram: device surface vs PDF page, showing actual scaling/rotation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._mode = "proportional"
        self._device_w = 13.0
        self._device_h = 8.0
        self._page_w = 210.0
        self._page_h = 297.0

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    def set_device_ar(self, w_cm: float, h_cm: float):
        self._device_w = w_cm if w_cm else 1.0
        self._device_h = h_cm if h_cm else 1.0
        self.update()

    def set_page_ar(self, w_mm: float, h_mm: float):
        self._page_w = w_mm if w_mm else 1.0
        self._page_h = h_mm if h_mm else 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#2b2b2b"))

        W, H = float(self.width()), float(self.height())
        pad = 16.0
        label_h = 20.0
        avail_w = W - 2 * pad
        avail_h = H - 2 * pad - label_h
        cx = W / 2
        cy = pad + avail_h / 2

        def fit_rect_centered(ar, max_w, max_h, ccx, ccy) -> QRectF:
            if ar > max_w / max_h:
                w, h = max_w, max_w / ar
            else:
                h, w = max_h, max_h * ar
            return QRectF(ccx - w / 2, ccy - h / 2, w, h)

        page_ar = self._page_w / self._page_h
        dev_w, dev_h = self._device_w, self._device_h

        # PDF page (grey) — fills available area
        page_rect = fit_rect_centered(page_ar, avail_w, avail_h, cx, cy)
        p.setPen(QPen(QColor("#888888"), 1.5))
        p.setBrush(QBrush(QColor("#3a3a3a")))
        p.drawRect(page_rect)

        if self._mode == "proportional":
            # Determine if rotation would be applied (same logic as fitting.py)
            uw, uh = page_rect.width(), page_rect.height()
            scale_normal  = min(uw / dev_w, uh / dev_h)
            scale_rotated = min(uw / dev_h, uh / dev_w)
            rotate = scale_rotated > scale_normal
            scale = scale_rotated if rotate else scale_normal

            # Device rect in page space after fitting (possibly rotated)
            if rotate:
                fitted_w = dev_h * scale
                fitted_h = dev_w * scale
                rot_label = " (rotated 90°)"
            else:
                fitted_w = dev_w * scale
                fitted_h = dev_h * scale
                rot_label = ""

            dev_fitted = QRectF(cx - fitted_w / 2, cy - fitted_h / 2, fitted_w, fitted_h)
            p.setPen(QPen(QColor("#ffaa44"), 1.5, Qt.DashLine))
            p.setBrush(QBrush(QColor(255, 170, 68, 40)))
            p.drawRect(dev_fitted)
            label = f"Proportional{rot_label}  —  device (orange) fitted onto page (grey)"
        else:
            # Scale to format: show full page filled
            p.setPen(QPen(QColor("#4488cc"), 1.5))
            p.setBrush(QBrush(QColor(68, 136, 204, 50)))
            p.drawRect(page_rect)
            label = "Scale to Format  —  strokes scaled to fill page"

        # Label
        p.setPen(QColor("#aaaaaa"))
        p.setFont(QFont("sans-serif", 9))
        p.drawText(QRectF(0, H - label_h, W, label_h), Qt.AlignCenter, label)

        p.end()


class _VectorLookPreview(QWidget):
    """Shows a sample curve getting smoother as smoothness increases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._smoothness = 50

    def set_smoothness(self, value: int):
        self._smoothness = value
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#2b2b2b"))

        W, H = self.width(), self.height()
        pad = 16

        # Generate a jagged reference polyline
        import math
        n = 12
        raw = []
        for i in range(n):
            x = pad + (W - 2 * pad) * i / (n - 1)
            y = H / 2 + (H / 3) * math.sin(i * 1.3) * (0.5 + 0.5 * math.cos(i * 0.7))
            raw.append((x, y))

        # Apply RDP + Chaikin (same pipeline as PDF output)
        from pdf_builder import _chaikin, _smoothness_to_iterations, _rdp_simplify, _smoothness_to_epsilon  # type: ignore
        eps = _smoothness_to_epsilon(self._smoothness, raw)
        pts = _rdp_simplify(raw, eps) if eps > 0 else raw
        iters = _smoothness_to_iterations(self._smoothness)
        pts = _chaikin(pts, iters)

        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)

        pen = QPen(QColor("#44cc88"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)
        p.end()


class ConfigDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)
        self._cfg = copy.deepcopy(cfg)  # work on a copy; only apply on OK
        self._selected_printer_name: str = cfg.printer_name  # needed before _build_ui

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._tab_print_format(), "Print Format")
        self._tabs.addTab(self._tab_mouse(), "Input")
        self._tabs.addTab(self._tab_fitting(), "Scaling")
        self._tabs.addTab(self._tab_line_and_vector(), "Vector")
        self._tabs.addTab(self._tab_num_lines(), "Number of Strokes")
        self._tabs.addTab(self._tab_archive(), "Archive Folder")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- Print Format (merged) ---
    def _tab_print_format(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._pdf_preset = QComboBox()
        self._pdf_preset.setMaximumWidth(180)
        self._pdf_preset.currentTextChanged.connect(self._update_fitting_preview)
        layout.addRow("Paper format:", self._pdf_preset)

        self._bg_color_btn = _ColorButton(self._cfg.background_color)
        layout.addRow("Background colour:", self._bg_color_btn)

        self._dpi = QSpinBox()
        self._dpi.setRange(72, 2400)
        self._dpi.setSingleStep(72)
        self._dpi.setMaximumWidth(100)
        layout.addRow("Print Resolution (DPI):", self._dpi)

        # Printer via system print dialog
        printer_row = QWidget()
        printer_layout = QHBoxLayout(printer_row)
        printer_layout.setContentsMargins(0, 0, 0, 0)
        self._printer_label = QLabel("(system default)")
        self._printer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        select_btn = QPushButton("Select Printer…")
        select_btn.clicked.connect(self._on_select_printer)
        printer_layout.addWidget(self._printer_label)
        printer_layout.addWidget(select_btn)
        layout.addRow("Printer:", printer_row)

        self._save_pdf_only = QCheckBox("Save to PDF only (do not send to printer)")
        layout.addRow(self._save_pdf_only)

        # Populate paper sizes for default printer
        self._refresh_paper_presets()

        return w

    def _refresh_paper_presets(self):
        """Re-populate the paper format combo with sizes supported by the selected printer."""
        current = self._pdf_preset.currentText()
        if self._selected_printer_name:
            info = QPrinterInfo.printerInfo(self._selected_printer_name)
        else:
            info = QPrinterInfo.defaultPrinter()
        supported = info.supportedPageSizes()
        our_keys = set(PAPER_SIZES_MM.keys()) - {"Custom"}
        if supported:
            names = [ps.key() for ps in supported if ps.key() in our_keys]
        else:
            names = []
        if not names:
            # Fallback: show all known sizes
            names = sorted(our_keys, key=lambda k: list(PAPER_SIZES_MM).index(k))
        self._pdf_preset.blockSignals(True)
        self._pdf_preset.clear()
        self._pdf_preset.addItems(names)
        # Restore previous selection if still available
        idx = self._pdf_preset.findText(current)
        if idx >= 0:
            self._pdf_preset.setCurrentIndex(idx)
        self._pdf_preset.blockSignals(False)
        if hasattr(self, "_fit_prop"):
            self._update_fitting_preview()

    def _on_select_printer(self):
        printer = QPrinter()
        if self._selected_printer_name:
            printer.setPrinterName(self._selected_printer_name)
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            self._selected_printer_name = printer.printerName()
            self._printer_label.setText(self._selected_printer_name or "(system default)")
            self._refresh_paper_presets()

    # --- Fitting Options ---
    def _tab_fitting(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        mode_group = QGroupBox("Input mapping mode")
        mode_layout = QVBoxLayout(mode_group)
        self._fit_scale = QRadioButton("Center drawing (\"rotate and scale to format\")")
        self._fit_prop = QRadioButton("Map screen to format")
        self._fit_prop.setChecked(True)
        mode_layout.addWidget(self._fit_scale)
        mode_layout.addWidget(self._fit_prop)
        layout.addWidget(mode_group)

        self._unlimited_canvas = QCheckBox(
            "Unlimited canvas  (mouse drives an infinite drawing surface)"
        )
        layout.addWidget(self._unlimited_canvas)

        dev_group = QGroupBox("Physical input device size (for center screen mode)")
        dev_layout = QFormLayout(dev_group)
        self._dev_w = QDoubleSpinBox()
        self._dev_w.setRange(1.0, 100.0)
        self._dev_w.setDecimals(1)
        self._dev_w.setSuffix(" cm")
        self._dev_h = QDoubleSpinBox()
        self._dev_h.setRange(1.0, 100.0)
        self._dev_h.setDecimals(1)
        self._dev_h.setSuffix(" cm")
        dev_layout.addRow("Device width:", self._dev_w)
        dev_layout.addRow("Device height:", self._dev_h)
        layout.addWidget(dev_group)

        self._fitting_preview = _FittingPreview()
        layout.addWidget(QLabel("Preview:"))
        layout.addWidget(self._fitting_preview)

        # Connect signals for live preview updates
        self._fit_prop.toggled.connect(self._update_fitting_preview)
        self._fit_scale.toggled.connect(self._update_fitting_preview)
        self._dev_w.valueChanged.connect(self._update_fitting_preview)
        self._dev_h.valueChanged.connect(self._update_fitting_preview)

        layout.addStretch()
        return w

    def _update_fitting_preview(self):
        mode = "proportional" if self._fit_prop.isChecked() else "scale_to_format"
        self._fitting_preview.set_mode(mode)
        self._fitting_preview.set_device_ar(self._dev_w.value(), self._dev_h.value())
        w_mm = self._pdf_to_mm_w()
        h_mm = self._pdf_to_mm_h()
        self._fitting_preview.set_page_ar(w_mm, h_mm)

    def _pdf_to_mm_w(self) -> float:
        preset = self._pdf_preset.currentText()
        w_mm, _ = PAPER_SIZES_MM.get(preset, (210.0, 297.0))
        return w_mm

    def _pdf_to_mm_h(self) -> float:
        preset = self._pdf_preset.currentText()
        _, h_mm = PAPER_SIZES_MM.get(preset, (210.0, 297.0))
        return h_mm

    # --- Line & Vector (merged) ---
    def _tab_line_and_vector(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Smoothness slider
        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Precise"))
        label_row.addStretch()
        label_row.addWidget(QLabel("Smooth"))
        layout.addLayout(label_row)

        self._smooth_slider = QSlider(Qt.Horizontal)
        self._smooth_slider.setRange(0, 100)
        self._smooth_slider.setTickInterval(10)
        self._smooth_slider.setTickPosition(QSlider.TicksBelow)
        layout.addWidget(self._smooth_slider)

        # Vector preview
        self._vector_preview = _VectorLookPreview()
        layout.addWidget(self._vector_preview)
        self._smooth_slider.valueChanged.connect(self._vector_preview.set_smoothness)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Line controls
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setContentsMargins(0, 0, 0, 0)

        self._line_thickness = QDoubleSpinBox()
        self._line_thickness.setRange(0.1, 100.0)
        self._line_thickness.setDecimals(1)
        self._line_thickness.setSuffix(" pt")
        self._line_thickness.setMaximumWidth(100)
        form.addRow("Contour:", self._line_thickness)

        timing_row = QWidget()
        timing_layout = QHBoxLayout(timing_row)
        timing_layout.setContentsMargins(0, 0, 0, 0)
        self._thick_before = QRadioButton("Before fitting")
        self._thick_after = QRadioButton("After fitting")
        self._thick_after.setChecked(True)
        timing_layout.addWidget(self._thick_before)
        timing_layout.addWidget(self._thick_after)
        timing_layout.addStretch()
        form.addRow("Apply Contour:", timing_row)

        self._line_color_btn = _ColorButton(self._cfg.line_color)
        form.addRow("Line colour:", self._line_color_btn)

        self._bg_color_btn = _ColorButton(self._cfg.background_color)
        form.addRow("Background colour:", self._bg_color_btn)

        self._transparent_background = QCheckBox("Transparent background")
        form.addRow("", self._transparent_background)

        layout.addLayout(form)
        layout.addStretch()
        return w
        timing_layout = QHBoxLayout(timing_row)
        timing_layout.setContentsMargins(0, 0, 0, 0)
        self._thick_before = QRadioButton("Before fitting")
        self._thick_after = QRadioButton("After fitting")
        self._thick_after.setChecked(True)
        timing_layout.addWidget(self._thick_before)
        timing_layout.addWidget(self._thick_after)
        timing_layout.addStretch()
        form.addRow("Apply Contour:", timing_row)

        layout.addLayout(form)
        layout.addStretch()
        return w

    # --- Number of Lines ---
    def _tab_num_lines(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._num_lines = QSpinBox()
        self._num_lines.setRange(1, 100)
        self._num_lines.setMaximumWidth(80)
        layout.addRow(
            "Default strokes before printing (works on a limited canvas only):",
            self._num_lines,
        )

        note = QLabel(
            "Tip: right-click on the canvas to change this value on the fly.\n"
            "The setting persists across sessions."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: grey; font-size: 11px;")
        layout.addRow(note)

        return w

    # --- Archive Folder ---
    def _tab_archive(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("Archive folder (printed PDFs saved here with timestamp filename):"))

        row = QHBoxLayout()
        self._archive_path = QLineEdit()
        self._archive_path.setReadOnly(True)
        row.addWidget(self._archive_path)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_archive)
        row.addWidget(browse_btn)
        layout.addLayout(row)
        layout.addStretch()
        return w

    def _browse_archive(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select archive folder", self._archive_path.text() or str(Path.home())
        )
        if folder:
            self._archive_path.setText(folder)

    # --- Mouse Setup ---
    def _tab_mouse(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._input_device = QComboBox()
        self._input_device.setMaximumWidth(200)
        self._input_device.addItem("(system default)", "")
        try:
            from PyQt5.QtGui import QInputDevice  # type: ignore
            for dev in QInputDevice.devices():
                self._input_device.addItem(dev.name(), dev.name())
        except (ImportError, AttributeError):
            pass

        layout.addRow("Input device:", self._input_device)

        note = QLabel("Select the device used for drawing. Use '(system default)' for mouse or trackpad.")
        note.setWordWrap(True)
        note.setStyleSheet("color: grey; font-size: 11px;")
        layout.addRow(note)
        return w



    # ------------------------------------------------------------------ #
    #  Load / Apply Values                                                  #
    # ------------------------------------------------------------------ #

    def _load_values(self):
        cfg = self._cfg

        # Print Format — preset list already populated by _refresh_paper_presets()
        idx = self._pdf_preset.findText(cfg.paper_preset)
        if idx >= 0:
            self._pdf_preset.setCurrentIndex(idx)
        elif self._pdf_preset.count() > 0:
            self._pdf_preset.setCurrentIndex(0)
        self._dpi.setValue(cfg.dpi)
        self._bg_color_btn._color = QColor(cfg.background_color)
        self._bg_color_btn._refresh()

        # Fitting
        if cfg.fitting_mode == "scale_to_format":
            self._fit_scale.setChecked(True)
        else:
            self._fit_prop.setChecked(True)
        self._dev_w.setValue(cfg.device_width_cm)
        self._dev_h.setValue(cfg.device_height_cm)
        self._unlimited_canvas.setChecked(cfg.unlimited_canvas)
        self._update_fitting_preview()

        # Line config
        self._line_thickness.setValue(cfg.line_thickness_pt)
        self._line_color_btn._color = QColor(cfg.line_color)
        self._line_color_btn._refresh()
        self._transparent_background.setChecked(cfg.transparent_background)
        if cfg.thickness_timing == "before":
            self._thick_before.setChecked(True)
        else:
            self._thick_after.setChecked(True)

        # Vector look
        self._smooth_slider.setValue(cfg.smoothness)

        # Number of lines
        self._num_lines.setValue(cfg.default_line_count)

        # Archive
        self._archive_path.setText(cfg.archive_folder)

        # Input device
        dev_idx = self._input_device.findData(cfg.input_device)
        if dev_idx >= 0:
            self._input_device.setCurrentIndex(dev_idx)

        # Printer
        self._selected_printer_name = cfg.printer_name
        self._printer_label.setText(cfg.printer_name or "(system default)")
        self._save_pdf_only.setChecked(cfg.save_pdf_only)

    def _on_ok(self):
        cfg = self._cfg

        # Print Format
        cfg.paper_preset = self._pdf_preset.currentText()
        cfg.pdf_width_mm = self._pdf_to_mm_w()
        cfg.pdf_height_mm = self._pdf_to_mm_h()
        cfg.dpi = self._dpi.value()
        cfg.background_color = self._bg_color_btn.color_hex()

        # Fitting
        cfg.fitting_mode = "proportional" if self._fit_prop.isChecked() else "scale_to_format"
        cfg.device_width_cm = self._dev_w.value()
        cfg.device_height_cm = self._dev_h.value()
        cfg.unlimited_canvas = self._unlimited_canvas.isChecked()

        # Line config
        cfg.line_thickness_pt = self._line_thickness.value()
        cfg.line_color = self._line_color_btn.color_hex()
        cfg.transparent_background = self._transparent_background.isChecked()
        cfg.thickness_timing = "before" if self._thick_before.isChecked() else "after"

        # Vector look
        cfg.smoothness = self._smooth_slider.value()

        # Number of lines
        cfg.default_line_count = self._num_lines.value()

        # Archive
        cfg.archive_folder = self._archive_path.text()

        # Input device
        cfg.input_device = self._input_device.currentData() or ""

        # Printer
        cfg.printer_name = self._selected_printer_name or ""
        cfg.save_pdf_only = self._save_pdf_only.isChecked()

        save_config(cfg)
        self.accept()

    def get_config(self) -> Config:
        return self._cfg
