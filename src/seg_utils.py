"""Instance outlines from YOLO-seg results.

`result.masks.xy` merges several pieces of one instance into a single polygon (thin "bridges" appear),
so we compute the outlines from the masks ourselves — every piece separately. Needs predictions made
with retina_masks=True (masks at image resolution).

The model sometimes also returns one large instance covering several items (webcam test 2026-10-12:
2 toasts -> 3 detections). So instances of the same class that are >60% covered by more confident ones
are dropped, and area counts only new pixels — the same food is never counted twice.
"""
import cv2
import numpy as np


def instances(result, min_area_frac: float = 0.0, eps_frac: float = 0.002, dup_overlap: float = 0.6):
    """Returns a list of (class name, confidence, area in px not yet counted for this class, [polygons Nx2 in px])."""
    if result.masks is None:
        return []
    h, w = result.orig_shape
    masks = result.masks.data.cpu().numpy().astype(np.uint8)
    if masks.shape[1:] != (h, w):  # without retina_masks: resize to the image size
        masks = np.stack([cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST) for m in masks])
    names = [result.names[int(c)] for c in result.boxes.cls.tolist()]
    confs = result.boxes.conf.tolist()
    covered = {}  # class -> union of the masks accepted so far
    out = []
    for i in sorted(range(len(masks)), key=lambda k: -confs[k]):
        m, name = masks[i].astype(bool), names[i]
        area = int(m.sum())
        if area == 0:
            continue
        prev = covered.setdefault(name, np.zeros((h, w), bool))
        if (m & prev).sum() > dup_overlap * area:
            continue
        new_px = int((m & ~prev).sum())
        prev |= m
        contours, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys = []
        for c in contours:
            if cv2.contourArea(c) < max(min_area_frac * h * w, 4):
                continue
            c = cv2.approxPolyDP(c, eps_frac * cv2.arcLength(c, True), True).reshape(-1, 2)
            if len(c) >= 3:
                polys.append(c.astype(np.float32))
        if polys:
            out.append((name, float(confs[i]), float(new_px), polys))
    return out
