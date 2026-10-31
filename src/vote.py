"""Multi-frame voting: the plate is photographed several times within ~0.4 s, every frame is recognized
separately, and each region of the plate gets the class most frames agree on. This means fewer flips between
similar classes (toast/bread) and fewer one-frame ghosts.

Predictions are made with a low threshold (conf 0.05) on purpose: the weaker classes the model also considered
for a region become the alternatives for the CHANGE button on the display. A region is kept only if it was
detected with the normal threshold in most frames.
"""
import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Region:
    rep: np.ndarray                               # mask (model resolution) of the most confident detection
    small: np.ndarray                             # downsampled mask, for fast overlap tests
    frames: dict = field(default_factory=dict)    # frame -> {class: best confidence}
    areas: dict = field(default_factory=dict)     # class -> [area in image pixels]
    name: str = ""
    conf: float = 0.0
    area: float = 0.0
    scores: dict = field(default_factory=dict)    # class -> confidence averaged over all frames
    polys: list = field(default_factory=list)     # outlines at image resolution


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    return np.logical_and(a, b).sum() / (np.logical_or(a, b).sum() + 1e-9)


def vote(results: list, conf_thr: float = 0.35, iou_thr: float = 0.5, min_frac: float = 0.5,
         dup_overlap: float = 0.6) -> list[Region]:
    k = len(results)
    h, w = results[0].orig_shape
    insts = []
    for f, r in enumerate(results):
        if r.masks is None:
            continue
        masks = r.masks.data.cpu().numpy().astype(bool)
        for m, cls, conf in zip(masks, r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            insts.append((f, r.names[int(cls)], conf, m))
    if not insts:
        return []
    scale = h * w / insts[0][3].size  # mask pixels -> image pixels

    regions: list[Region] = []
    for f, name, conf, m in sorted(insts, key=lambda t: -t[2]):
        small = m[::4, ::4]
        reg = next((r for r in regions if _iou(small, r.small) > iou_thr), None)
        if reg is None:
            reg = Region(rep=m, small=small)
            regions.append(reg)
        seen = reg.frames.setdefault(f, {})
        seen[name] = max(seen.get(name, 0.0), conf)
        reg.areas.setdefault(name, []).append(float(m.sum()) * scale)

    kept = []
    for reg in regions:
        sure_frames = sum(1 for cls in reg.frames.values() if max(cls.values()) >= conf_thr)
        if sure_frames < math.ceil(k * min_frac):
            continue
        scores = {}
        for cls in reg.frames.values():
            for n, c in cls.items():
                scores[n] = scores.get(n, 0.0) + c / k
        reg.scores = dict(sorted(scores.items(), key=lambda kv: -kv[1]))
        reg.name, reg.conf = next(iter(reg.scores.items()))
        reg.area = float(np.median(reg.areas[reg.name]))
        kept.append(reg)

    # the same food counted twice (e.g. one big detection over two toasts): drop regions mostly covered by
    # more confident regions of the same class, otherwise count only the new pixels
    covered, out = {}, []
    for reg in sorted(kept, key=lambda r: -r.conf):
        prev = covered.setdefault(reg.name, np.zeros_like(reg.rep))
        overlap = (reg.rep & prev).sum() / max(reg.rep.sum(), 1)
        if overlap > dup_overlap:
            continue
        reg.area *= 1 - overlap
        prev |= reg.rep
        full = cv2.resize(reg.rep.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        contours, _ = cv2.findContours(full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        reg.polys = [cv2.approxPolyDP(c, 0.003 * cv2.arcLength(c, True), True).reshape(-1, 2).astype(float)
                     for c in contours if cv2.contourArea(c) > 0.001 * h * w]
        out.append(reg)
    return out
