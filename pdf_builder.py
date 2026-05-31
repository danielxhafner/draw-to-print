from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import List, Tuple

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import mm, inch, cm
from reportlab.lib.colors import HexColor

from config_manager import Config, PAPER_SIZES_MM
from fitting import transform_strokes

Point = Tuple[float, float]
Stroke = List[Point]

MM_TO_PT = 72.0 / 25.4


def _paper_size_pt(cfg: Config) -> Tuple[float, float]:
    """Return (width_pt, height_pt) from config."""
    w_mm = cfg.pdf_width_mm
    h_mm = cfg.pdf_height_mm
    return w_mm * MM_TO_PT, h_mm * MM_TO_PT


def _rdp_simplify(points: List[Point], epsilon: float) -> List[Point]:
    """Ramer-Douglas-Peucker polyline simplification."""
    if len(points) < 3 or epsilon <= 0:
        return points
    start, end = points[0], points[-1]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    line_len = math.hypot(dx, dy)
    if line_len == 0:
        dists = [math.hypot(p[0] - start[0], p[1] - start[1]) for p in points[1:-1]]
    else:
        dists = [
            abs(dy * p[0] - dx * p[1] + end[0] * start[1] - end[1] * start[0]) / line_len
            for p in points[1:-1]
        ]
    max_dist = max(dists)
    max_idx = dists.index(max_dist) + 1
    if max_dist > epsilon:
        left = _rdp_simplify(points[:max_idx + 1], epsilon)
        right = _rdp_simplify(points[max_idx:], epsilon)
        return left[:-1] + right
    return [start, end]


def _smoothness_to_epsilon(smoothness: int, points: List[Point]) -> float:
    """Map smoothness 0–100 to an RDP epsilon relative to stroke extent."""
    if smoothness == 0 or len(points) < 2:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    extent = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    return (smoothness / 100) * extent * 0.025  # up to 2.5% of stroke extent


def _chaikin(points: List[Point], iterations: int) -> List[Point]:
    """Chaikin corner-cutting smoothing."""
    if len(points) < 3 or iterations == 0:
        return points
    result = points
    for _ in range(iterations):
        new_pts: List[Point] = [result[0]]
        for i in range(len(result) - 1):
            x0, y0 = result[i]
            x1, y1 = result[i + 1]
            new_pts.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            new_pts.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        new_pts.append(result[-1])
        result = new_pts
    return result


def _smoothness_to_iterations(smoothness: int) -> int:
    """Map 0–100 smoothness to 0–6 Chaikin iterations."""
    return round(smoothness / 100 * 6)


def build_pdf(
    strokes: List[Stroke],
    cfg: Config,
    canvas_w: float,
    canvas_h: float,
) -> Path:
    """
    Build a vector PDF from strokes, apply fitting transform and smoothing.
    Returns the path to a temporary PDF file.
    """
    pdf_w_pt, pdf_h_pt = _paper_size_pt(cfg)

    # Apply thickness before fitting if configured
    line_w = cfg.line_thickness_pt

    # Apply fitting transform. With unlimited canvas, strokes are stored
    # in world coords that extend past the screen; only the bbox-based
    # scale_to_format mapping makes sense.
    fit_mode = "scale_to_format" if cfg.unlimited_canvas else cfg.fitting_mode
    transformed, effective_scale = transform_strokes(
        strokes,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        pdf_w_pt=pdf_w_pt,
        pdf_h_pt=pdf_h_pt,
        mode=fit_mode,
        device_w_cm=cfg.device_width_cm,
        device_h_cm=cfg.device_height_cm,
    )

    if cfg.thickness_timing == "before":
        line_w *= effective_scale

    # Apply smoothing: RDP simplification first, then Chaikin curve fitting
    iterations = _smoothness_to_iterations(cfg.smoothness)
    smoothed = []
    for s in transformed:
        if len(s) < 2:
            continue
        eps = _smoothness_to_epsilon(cfg.smoothness, s)
        simplified = _rdp_simplify(s, eps) if eps > 0 else s
        smoothed.append(_chaikin(simplified, iterations))

    # Write PDF
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    out_path = Path(tmp.name)

    c = rl_canvas.Canvas(str(out_path), pagesize=(pdf_w_pt, pdf_h_pt))

    # Background fill
    if not cfg.transparent_background:
        bg = HexColor(cfg.background_color)
        c.setFillColor(bg)
        c.rect(0, 0, pdf_w_pt, pdf_h_pt, fill=1, stroke=0)

    # Draw strokes
    line_color = HexColor(cfg.line_color)
    c.setStrokeColor(line_color)
    c.setLineWidth(line_w)
    c.setLineCap(1)   # round caps
    c.setLineJoin(1)  # round joins

    for stroke in smoothed:
        if len(stroke) < 2:
            continue
        path = c.beginPath()
        path.moveTo(stroke[0][0], stroke[0][1])
        if len(stroke) == 2:
            path.lineTo(stroke[1][0], stroke[1][1])
        else:
            # Draw as cubic bezier segments through the points
            i = 1
            while i < len(stroke) - 1:
                x0, y0 = stroke[i - 1]
                x1, y1 = stroke[i]
                x2, y2 = stroke[i + 1]
                # Control points: mid-points between consecutive points
                mx0 = (x0 + x1) / 2
                my0 = (y0 + y1) / 2
                mx1 = (x1 + x2) / 2
                my1 = (y1 + y2) / 2
                path.curveTo(mx0, my0, x1, y1, mx1, my1)
                i += 1
            path.lineTo(stroke[-1][0], stroke[-1][1])
        c.drawPath(path, stroke=1, fill=0)

    c.save()
    return out_path

