from __future__ import annotations

from typing import List, Tuple

Point = Tuple[float, float]
Stroke = List[Point]


def _bounding_box(strokes: List[Stroke]) -> Tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) across all points in all strokes."""
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    if not xs:
        return 0.0, 0.0, 1.0, 1.0
    return min(xs), min(ys), max(xs), max(ys)


def transform_strokes(
    strokes: List[Stroke],
    canvas_w: float,
    canvas_h: float,
    pdf_w_pt: float,
    pdf_h_pt: float,
    mode: str,
    device_w_cm: float = 13.0,
    device_h_cm: float = 8.0,
) -> List[Stroke]:
    """
    Transform raw input strokes into PDF coordinate space (points, origin bottom-left).

    mode == "proportional":
        The physical device surface is letterboxed into the canvas.
        Strokes are remapped from that letterboxed region into the full PDF page.

    mode == "scale_to_format":
        Raw coordinates (which may exceed canvas bounds) are used as-is.
        Their bounding box is scaled/translated to fill the PDF page.
    """
    if not strokes or all(len(s) == 0 for s in strokes):
        return strokes

    if mode == "proportional":
        return _proportional(strokes, canvas_w, canvas_h, device_w_cm, device_h_cm, pdf_w_pt, pdf_h_pt)
    else:
        return _scale_to_format(strokes, pdf_w_pt, pdf_h_pt)


def _proportional(
    strokes: List[Stroke],
    canvas_w: float,
    canvas_h: float,
    device_w_cm: float,
    device_h_cm: float,
    pdf_w_pt: float,
    pdf_h_pt: float,
) -> List[Stroke]:
    """
    Fit the physical device area proportionally onto the PDF page, no stretching.
    Auto-rotates 90° if the device AR fits the page better that way.
    Strokes outside the device area are clamped to its boundary.
    """
    device_ar = device_w_cm / device_h_cm if device_h_cm else 1.0
    canvas_ar = canvas_w / canvas_h if canvas_h else 1.0

    # Letterbox region of the device on the canvas
    if device_ar > canvas_ar:
        mapped_w = canvas_w
        mapped_h = canvas_w / device_ar
        off_x = 0.0
        off_y = (canvas_h - mapped_h) / 2.0
    else:
        mapped_h = canvas_h
        mapped_w = canvas_h * device_ar
        off_x = (canvas_w - mapped_w) / 2.0
        off_y = 0.0

    # Page usable area with 5% margin
    margin_x = pdf_w_pt * 0.05
    margin_y = pdf_h_pt * 0.05
    usable_w = pdf_w_pt - 2 * margin_x
    usable_h = pdf_h_pt - 2 * margin_y

    # Decide rotation using physical device dimensions vs page dimensions
    scale_normal  = min(usable_w / device_w_cm, usable_h / device_h_cm)
    scale_rotated = min(usable_w / device_h_cm, usable_h / device_w_cm)
    rotate = scale_rotated > scale_normal
    scale = scale_rotated if rotate else scale_normal  # pts per cm

    # Centre of device region in canvas, and centre of page
    dev_cx = off_x + mapped_w / 2.0
    dev_cy = off_y + mapped_h / 2.0
    page_cx = margin_x + usable_w / 2.0
    page_cy = margin_y + usable_h / 2.0

    result: List[Stroke] = []
    for stroke in strokes:
        new_stroke: Stroke = []
        for x, y in stroke:
            # Clamp to device region on canvas
            cx = max(off_x, min(off_x + mapped_w, x))
            cy = max(off_y, min(off_y + mapped_h, y))
            # Device-relative offset in physical cm
            dx = (cx - dev_cx) / mapped_w * device_w_cm
            dy = (cy - dev_cy) / mapped_h * device_h_cm
            # Map to PDF coords (y-up); optionally rotate 90° CCW
            if rotate:
                px = page_cx + (-dy) * scale
                py = page_cy + dx * scale
            else:
                px = page_cx + dx * scale
                py = page_cy - dy * scale   # flip Y: canvas y-down → PDF y-up
            new_stroke.append((px, py))
        result.append(new_stroke)
    return result


def _scale_to_format(strokes: List[Stroke], pdf_w_pt: float, pdf_h_pt: float) -> List[Stroke]:
    """
    Scale the bounding box of all strokes to fit the PDF page proportionally,
    rotating 90° if that yields a larger fit. Centred with 5% margin.
    """
    min_x, min_y, max_x, max_y = _bounding_box(strokes)
    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0

    margin_frac = 0.05
    margin_x = pdf_w_pt * margin_frac
    margin_y = pdf_h_pt * margin_frac
    usable_w = pdf_w_pt - 2 * margin_x
    usable_h = pdf_h_pt - 2 * margin_y

    # Scale that fits without rotation
    scale_normal = min(usable_w / span_x, usable_h / span_y)
    # Scale that fits with 90° rotation (swap drawing axes onto page)
    scale_rotated = min(usable_w / span_y, usable_h / span_x)

    rotate = scale_rotated > scale_normal
    scale = scale_rotated if rotate else scale_normal

    # Centre of drawing bounding box
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    # Centre of usable page area (PDF origin bottom-left, y up)
    page_cx = margin_x + usable_w / 2.0
    page_cy = margin_y + usable_h / 2.0

    result: List[Stroke] = []
    for stroke in strokes:
        new_stroke: Stroke = []
        for x, y in stroke:
            dx = (x - cx) * scale
            dy = (y - cy) * scale
            if rotate:
                # Rotate 90° CCW: (dx, dy) -> (-dy, dx)
                px = page_cx + (-dy)
                py = page_cy + dx          # PDF y already increases upward here
            else:
                px = page_cx + dx
                py = page_cy - dy          # flip Y: canvas y-down -> PDF y-up
            new_stroke.append((px, py))
        result.append(new_stroke)
    return result


def _fit_to_page(
    normalised: List[Stroke],
    pdf_w_pt: float,
    pdf_h_pt: float,
) -> List[Stroke]:
    """
    Map normalised [0,1] coordinates to PDF points (origin bottom-left, y inverted).
    Auto-rotates 90° if that yields a larger fit. Adds 5% margin on all sides.
    The normalised coords carry the device aspect ratio (span_x=1, span_y=1/device_ar).
    """
    margin_x = pdf_w_pt * 0.05
    margin_y = pdf_h_pt * 0.05
    usable_w = pdf_w_pt - 2 * margin_x
    usable_h = pdf_h_pt - 2 * margin_y

    # Determine whether rotating 90° gives a better fit.
    # Normalised coords span [0,1] x [0,1] (device AR baked in).
    # Normal fit: scale = min(usable_w/1, usable_h/1)
    # Rotated fit: swap width/height axes
    scale_normal = min(usable_w, usable_h)      # span is 1 in each axis
    scale_rotated = min(usable_h, usable_w)     # same value — need AR to differ
    # Use actual device AR from the normalised bounding box
    all_pts = [p for s in normalised for p in s]
    if all_pts:
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        span_x = max(xs) - min(xs) or 1.0
        span_y = max(ys) - min(ys) or 1.0
    else:
        span_x = span_y = 1.0

    scale_normal = min(usable_w / span_x, usable_h / span_y)
    scale_rotated = min(usable_w / span_y, usable_h / span_x)
    rotate = scale_rotated > scale_normal

    page_cx = margin_x + usable_w / 2.0
    page_cy = margin_y + usable_h / 2.0
    cx = (max(xs) + min(xs)) / 2.0 if all_pts else 0.5
    cy = (max(ys) + min(ys)) / 2.0 if all_pts else 0.5
    scale = scale_rotated if rotate else scale_normal

    result: List[Stroke] = []
    for stroke in normalised:
        new_stroke: Stroke = []
        for nx, ny in stroke:
            dx = (nx - cx) * scale
            dy = (ny - cy) * scale
            if rotate:
                # Rotate 90° CCW then flip Y for PDF
                px = page_cx + dy           # was -dy in scale_to_format; here ny is already canvas-flipped
                py = page_cy + dx
            else:
                px = page_cx + dx
                py = page_cy - dy           # flip Y: normalised y-down → PDF y-up
            new_stroke.append((px, py))
        result.append(new_stroke)
    return result
